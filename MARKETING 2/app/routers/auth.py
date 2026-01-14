from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select
from app.database import get_db
from app.models import User
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
    
    # Create new user
    new_user = User(
        email=user.email,
        hashed_password=user.password + "not_really_hashed_for_demo", 
        referral_code=f"REF-{user.email.split('@')[0]}",
        tier="student"
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return {"id": new_user.id, "email": new_user.email, "referral_code": new_user.referral_code}

@router.get("/referral/{code}")
async def check_referral(code: str, db = Depends(get_db)):
    result = await db.execute(select(User).where(User.referral_code == code))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Referral code not found")
    return {"valid": True, "referrer": user.email}
