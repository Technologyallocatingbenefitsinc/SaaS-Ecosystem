from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import SlideDeck
from app.routers import auth

router = APIRouter()

@router.get("/recent-activity")
async def get_recent_activity(user = Depends(auth.get_replit_user), db: AsyncSession = Depends(get_db)):
    if not user:
        return []
        
    result = await db.execute(
        select(SlideDeck).where(SlideDeck.user_id == user.id).order_by(SlideDeck.created_at.desc()).limit(5)
    )
    recent_decks = result.scalars().all()
    
    return [
        {
            "id": deck.id,
            "title": "Video Summary", 
            "date": deck.created_at.strftime("%b %d, %Y") if deck.created_at else "Recently",
            "url": deck.video_url,
            "preview": deck.summary_content[:100] + "..." if deck.summary_content else ""
        }
        for deck in recent_decks
    ]
