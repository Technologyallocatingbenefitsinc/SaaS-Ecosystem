import pytest
from app.main import app
from httpx import AsyncClient, ASGITransport
from app.models import AnalyticsEvent
from app.database import get_db
from sqlalchemy.future import select

from app.database import Base, engine

@pytest.mark.asyncio
async def test_analytics_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        
        # 1. Track an event (Video View)
        track_res = await ac.post("/api/analytics/track", json={
            "event_type": "VIEW_VIDEO",
            "resource_id": "https://youtube.com/watch?v=TEST12345",
            "metadata": '{"source": "test"}'
        })
        assert track_res.status_code == 200
        
        # 2. Track another event (different video)
        await ac.post("/api/analytics/track", json={
            "event_type": "VIEW_VIDEO",
            "resource_id": "https://youtube.com/watch?v=OTHER99",
        })
        
        # 3. Get Dashboard Stats
        # Note: In our mock setup, the dashboard fetches ALL events.
        stats_res = await ac.get("/api/analytics/dashboard")
        assert stats_res.status_code == 200
        data = stats_res.json()
        
        # Verify Total Interactions (at least 2 now)
        assert data["total_interactions"] >= 2
        
        # Verify Top Videos
        # Should contain TEST12345 and OTHER99
        top_videos = [v["video"] for v in data["top_videos"]]
        assert "https://youtube.com/watch?v=TEST12345" in top_videos
