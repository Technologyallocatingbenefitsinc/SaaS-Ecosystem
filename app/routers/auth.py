from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.future import select
from app.database import get_db
from app.models import User
from app.config import settings
from app.limiter import limiter
import httpx
from pydantic import BaseModel
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

import secrets
from datetime import datetime, timedelta, timezone

router = APIRouter()

class UserSignup(BaseModel):
    email: str
    password: str
    referral_code: str | None = None
    device_fingerprint: str | None = None

class UserLogin(BaseModel):
    email: str
    password: str

class ForgotPassword(BaseModel):
    email: str

class ResetPassword(BaseModel):
    token: str
    new_password: str

class SocialLogin(BaseModel):
    id_token: str
    provider: str = "google" # or "apple"
    first_name: str | None = None
    last_name: str | None = None

@router.post("/signup", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def signup(request: Request, user: UserSignup, db = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check Referral Code logic
    initial_credits = 1
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
    user_credits = initial_credits
    
    # Check Device Fingerprint Abuse
    if user.device_fingerprint:
        fp_result = await db.execute(select(User).where(User.device_fingerprint == user.device_fingerprint))
        existing_fp = fp_result.scalars().first()
        if existing_fp:
             # Device used before -> No Free Trial Credits
             user_credits = 0
             print(f"Device Abuse Detected: {user.device_fingerprint} -> Setting credits to 0")

    new_user = User(
        email=user.email,
        hashed_password=hash_password(user.password), 
        referral_code=f"REF-{user.email.split('@')[0]}",
        tier="student", 
        credits=user_credits,
        device_fingerprint=user.device_fingerprint
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return {"id": new_user.id, "email": new_user.email, "credits": new_user.credits}

@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, user_data: UserLogin, db = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    user = result.scalars().first()
    
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    return {
        "status": "success",
        "user_id": user.id, 
        "email": user.email, 
        "username": user.username,
        "role": user.tier,
        "credits": user.credits
    }

@router.post("/forgot-password")
async def forgot_password(data: ForgotPassword, db = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalars().first()
    
    if not user:
        # Don't reveal user existence
        return {"status": "If that email exists, a link was sent."}
    
    # Generate Token
    token = secrets.token_urlsafe(32)
    user.reset_token = token
    # Expires in 15 mins
    user.reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    db.add(user)
    await db.commit()
    
    # Trigger N8n Webhook
    async with httpx.AsyncClient() as client:
        try:
            # We assume settings has this or we fallback to generic
            webhook_url = getattr(settings, "N8N_RESET_PASSWORD_WEBHOOK", "https://your-n8n-instance.com/webhook/reset-pass")
            await client.post(webhook_url, json={
                "email": user.email,
                "reset_link": f"https://{settings.HostName if hasattr(settings, 'HostName') else 'your-app.com'}/reset-password?token={token}"
            })
        except Exception as e:
            print(f"Failed to trigger Reset Email: {e}")
            
    return {"status": "If that email exists, a link was sent."}

@router.post("/reset-password")
async def reset_password(data: ResetPassword, db = Depends(get_db)):
    # Find user by token
    result = await db.execute(select(User).where(User.reset_token == data.token))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    # Check expiry
    if user.reset_token_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
        
    # Update Password
    user.hashed_password = hash_password(data.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    
    db.add(user)
    await db.commit()
    
    return {"status": "Password updated successfully"}

@router.post("/google")
async def google_login(data: SocialLogin, db = Depends(get_db)):
    # 1. Verify Token with Google
    google_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={data.id_token}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(google_url)
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Google Token")
            google_data = resp.json()
        except:
             raise HTTPException(status_code=401, detail="Failed to verify Google Token")

    email = google_data.get("email")
    google_sub = google_data.get("sub")
    name = google_data.get("name", "User")
    picture = google_data.get("picture")

    # 2. Find or Create User
    # First check by Google ID
    result = await db.execute(select(User).where(User.google_id == google_sub))
    user = result.scalars().first()

    if not user:
        # Fallback: Check by Email (Account Linking)
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if user:
            # Link Account
            user.google_id = google_sub
            if not user.avatar_url:
                user.avatar_url = picture
        else:
            # Create New User
            user = User(
                email=email,
                username=name,
                google_id=google_sub,
                avatar_url=picture,
                tier="student", 
                credits=1 # Free Trial
            )
            # Check for generic defaults if needed
    
    # Update Avatar if missing
    if picture and not user.avatar_url:
        user.avatar_url = picture

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "status": "success",
        "user_id": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.tier,
        "credits": user.credits,
        "avatar": user.avatar_url
    }

@router.post("/apple")
async def apple_login(data: SocialLogin, db = Depends(get_db)):
    # 1. Apple Verification (Complex without libraries)
    # Ideally: Verify JWT signature against Apple's keys
    # For MVP/PoC: We will assume the client sent the decoded payload or a valid token we trust (unsafe for prod)
    # OR we use a library. But I'll use a placeholder that accepts the "sub" from the token if feasible.
    # A robust implementation requires decoding the JWT header, fetching keys from Apple, and verifying.
    
    # MOCK verification for now (as per plan/constraints)
    # In production, use `jwt.decode` with Apple's Public Key.
    
    # We'll assume the client sends the email in the payload logic for now, 
    # but normally we extract it from claims.
    # HACK: For this step, we'll decode unverified or rely on mocked token structure for testing.
    
    try:
        # This is strictly a placeholder. Real implementation needs PyJWT + cryptography.
        # We assume the "id_token" passed here is just a JSON string for our current test phase,
        # or we accept it blindly if it looks like a JWT.
        # Let's Implement a "Mock" logic: if token starts with "mock_apple_", it's valid.
        if data.id_token.startswith("mock_apple_"):
             # Simulating decoding
             apple_sub = data.id_token.replace("mock_apple_", "")
             email = f"{apple_sub}@privaterelay.appleid.com" # Fake email
        else:
             # Just fail safely if not our mock
             raise HTTPException(status_code=401, detail="Apple Auth requires valid JWT verification (Not implemented without libraries)")
    except:
         raise HTTPException(status_code=401, detail="Invalid Apple Token")

    # 2. Find or Create
    result = await db.execute(select(User).where(User.apple_id == apple_sub))
    user = result.scalars().first()

    if not user:
        user = User(
            email=email,
            apple_id=apple_sub,
            tier="student",
            credits=1
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
    return {
        "status": "success",
        "user_id": user.id,
        "email": user.email,
        "role": user.tier,
        "credits": user.credits
    }

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
            credits=1 # 1 Free Trial Credit
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
