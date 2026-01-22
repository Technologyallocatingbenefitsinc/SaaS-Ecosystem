from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.models import User, AnalyticsEvent, SlideDeck
from app.routers.auth import get_replit_user
from pydantic import BaseModel
from typing import Optional, List
import datetime

router = APIRouter(prefix="/analytics", tags=["analytics"])

class EventRequest(BaseModel):
    event_type: str
    resource_id: Optional[str] = None
    metadata: Optional[str] = None

@router.post("/track")
async def track_event(
    request: EventRequest,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_replit_user)
):
    try:
        user_id = user.id if user else None
        
        # If no user, we might still want to log it if we had a session ID, 
        # but for this MVP we'll focus on logged-in users or just log 'None'
        
        new_event = AnalyticsEvent(
            user_id=user_id,
            event_type=request.event_type,
            resource_id=request.resource_id,
            metadata_json=request.metadata
        )
        db.add(new_event)
        await db.commit()
        return {"status": "ok"}
    except Exception as e:
        print(f"Tracking Error: {e}")
        # Don't crash the client for analytics errors
        return {"status": "error", "detail": str(e)}

@router.get("/dashboard")
async def get_analytics_dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_replit_user)
):
    # Only allow professors (or for now, anyone for demo purposes)
    # in real app: if user.tier != "professor": raise HTTPException(403)
    
    try:
        # 1. Total Interactions (All time)
        total_query = select(func.count(AnalyticsEvent.id))
        total_result = await db.execute(total_query)
        total_interactions = total_result.scalar() or 0
        
        # 2. Top Videos (Group by resource_id) - Filter for VIEW_VIDEO
        top_videos_query = (
            select(AnalyticsEvent.resource_id, func.count(AnalyticsEvent.id).label("count"))
            .where(AnalyticsEvent.event_type == "VIEW_VIDEO")
            .where(AnalyticsEvent.resource_id != None)
            .group_by(AnalyticsEvent.resource_id)
            .order_by(desc("count"))
            .limit(5)
        )
        top_videos_res = await db.execute(top_videos_query)
        top_videos = [{"video": r[0], "views": r[1]} for r in top_videos_res.all()]
        
        # 3. Active Students (Unique user_ids in last 7 days)
        seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        active_students_query = (
            select(func.count(func.distinct(AnalyticsEvent.user_id)))
            .where(AnalyticsEvent.timestamp >= seven_days_ago)
            .where(AnalyticsEvent.user_id != None)
        )
        active_res = await db.execute(active_students_query)
        active_students = active_res.scalar() or 0
        
        return {
            "total_interactions": total_interactions,
            "top_videos": top_videos,
            "active_students_7d": active_students
        }
    except Exception as e:
        print(f"Analytics Dashboard Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
