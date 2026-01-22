from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SlideDeck
from app.routers.auth import get_replit_user

router = APIRouter()

@router.get("/recent-activity")
async def get_recent_activity(user = Depends(get_replit_user), db: Session = Depends(get_db)):
    if not user:
        return []
        
    recent_decks = db.query(SlideDeck).filter(
        SlideDeck.user_id == user.id
    ).order_by(SlideDeck.created_at.desc()).limit(5).all()
    
    return [
        {
            "id": deck.id,
            "title": "Video Summary", # We might want to parse title from content later, or store it.
            "date": deck.created_at.strftime("%b %d, %Y"),
            "url": deck.video_url,
            "preview": deck.summary_content[:100] + "..." if deck.summary_content else ""
        }
        for deck in recent_decks
    ]
