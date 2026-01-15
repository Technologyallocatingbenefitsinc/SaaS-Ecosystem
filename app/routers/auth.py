from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.future import select
from app.database import get_db
from app.models import User
from app.config import settings
import httpx
from pydantic import BaseModel

router = APIRouter()

class UserSignup(BaseModel):
    email: str
    password: str
    referral_code: str | None = None

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(user: UserSignup, db = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check Referral Code logic
    initial_credits = 0
    if user.referral_code:
        # Find referrer
        ref_result = await db.execute(select(User).where(User.referral_code == user.referral_code))
        referrer = ref_result.scalars().first()
        if referrer:
            # Reward Referrer (5 Credits)
            referrer.credits += 5
            initial_credits = 2 # Bonus for new user too? Let's say yes.
            db.add(referrer) # Mark for update

    # Create new user
    new_user = User(
        email=user.email,
        hashed_password=user.password + "not_really_hashed_for_demo", 
        referral_code=f"REF-{user.email.split('@')[0]}",
        tier="student", 
        credits=initial_credits
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return {"id": new_user.id, "email": new_user.email, "credits": new_user.credits}

@router.get("/referral/{code}")
async def check_referral(code: str, db = Depends(get_db)):
    result = await db.execute(select(User).where(User.referral_code == code))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Referral code not found")
    return {"valid": True, "referrer": user.email}

async def get_replit_user(request: Request, db = Depends(get_db)):
    """Dependency to extract Replit Auth headers and sync with DB"""
    user_id = request.headers.get("X-Replit-User-Id")
    user_name = request.headers.get("X-Replit-User-Name")
    user_roles = request.headers.get("X-Replit-User-Roles")

    if not user_id:
        return None

    # Sync with DB
    result = await db.execute(select(User).where(User.replit_id == user_id))
    user = result.scalars().first()

    if not user:
        # Create user if logging in via Replit for the first time
        user = User(
            email=f"{user_name}@replit.user", # Replit doesn't always provide email in headers
            replit_id=user_id,
            username=user_name,
            tier="student", # Default
            credits=5 # Welcome bonus
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    return user

@router.get("/me")
async def get_me(user = Depends(get_replit_user)):
    if not user:
        return {"logged_in": False}
    return {
        "logged_in": True,
        "id": user.id,
        "email": user.email,
        "username": getattr(user, 'username', 'User'),
        "role": user.tier,
        "credits": user.credits
    }

@router.get("/api/profile")
async def get_profile(user = Depends(get_replit_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return {
        "email": user.email,
        "username": user.username,
        "role": user.tier,
        "credits": user.credits,
        "referral_code": user.referral_code,
        "member_since": user.created_at.strftime("%B %Y")
    }

@router.post("/api/recovery")
async def manual_recovery(email: str, db = Depends(get_db)):
    """Triggers n8n alert for manual account recovery"""
    # In a real app, send to n8n webhook
    print(f"n8n Alert: Manual Recovery requested for {email}")
    return {"status": "Recovery request sent to support"}

@router.delete("/api/delete-account")
async def delete_account(
    user = Depends(get_replit_user), 
    db = Depends(get_db),
    x_n8n_auth: str = Header(None)
):
    """Triple-Wipe: DB, Storage, and Automation Purge"""
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # 1. Security Check (Optional but recommended for destructive actions)
    if x_n8n_auth and x_n8n_auth != settings.AUTH_SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid Auth Token for deletion")

    user_email = user.email
    user_id = user.id

    # 2. Storage Wipe (Videos, PDFs)
    from app.routers.upload import delete_user_folder
    await delete_user_folder(user_id)
    
    # 3. Automation Purge (Signal n8n)
    async with httpx.AsyncClient() as client:
        try:
            await client.post(settings.N8N_PURGE_WEBHOOK, json={
                "email": user_email,
                "event": "account_terminated",
                "auth_token": settings.AUTH_SECRET_TOKEN
            })
        except Exception as e:
            print(f"n8n Purge failed: {e}")

    # 4. Database Wipe
    await db.delete(user)
    await db.commit()
    
    return {"status": "Triple-Wipe Complete. Your data has been permanently erased."}

@router.post("/api/credits/add")
async def add_credits(
    user_id: int, 
    amount: int, 
    x_n8n_auth: str = Header(None),
    db = Depends(get_db)
):
    """Internal Webhook to add credits after payment success"""
    if x_n8n_auth != settings.AUTH_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.credits += amount
    db.add(user)
    await db.commit()
    
    return {"status": "success", "new_balance": user.credits}
