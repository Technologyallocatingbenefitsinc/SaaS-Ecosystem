from fastapi import FastAPI, Depends, HTTPException, Header, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.database import engine, get_db, Base
from app.config import settings
from app.services.gemini_engine import process_video_content
from app.routers import auth, editor, legal, upload

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables (if simplified flow)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

# Mount Static & Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(editor.router, prefix="/editor", tags=["editor"])
app.include_router(legal.router, prefix="/legal", tags=["legal"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])

@app.get("/")
def read_root():
    return {"message": "SaaS Ecosystem API is running"}

@app.post("/debug-fix")
async def handle_error(request: Request, x_n8n_auth: str = Header(None)):
    # Verify the signal is from your n8n
    if x_n8n_auth != settings.AUTH_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    error_data = await request.json()
    
    # 🚨 This log is picked up by Antigravity's Agent
    print(f"CRITICAL_ERROR_LOG: Node {error_data.get('node', 'Unknown')} failed. Message: {error_data.get('message', 'No message')}")
    
    return {"status": "Agent alerted for repair"}

@app.post("/process-video")
async def process_video_endpoint(
    video_url: str, 
    user_tier: str = "student",
    x_n8n_auth: str = Header(None),
    db = Depends(get_db)
):
    if x_n8n_auth != settings.AUTH_SECRET_TOKEN:
         raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        result = await process_video_content(video_url, user_tier)
        return result
    except Exception as e:
        print(f"Error processing video: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Mock User Data (In real app, fetch from DB)
    user_tier = "professor" # Change this to 'student' or 'podcaster' to see other views
    
    mock_stats = {
        "credits": 25,
        "tier": user_tier
    }
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        **mock_stats
    })

@app.post("/invite-students")
async def invite_students():
    # Trigger n8n Webhook for emails
    # In production: Fetch user's class list from DB
    async with httpx.AsyncClient() as client:
        try:
            # Replace with ACTUAL n8n Production URL
            # await client.post("https://your-n8n-instance.com/webhook/professor-invite", json={"professor_id": 123})
            print("Simulating n8n Invite Webhook Trigger...")
            pass 
        except Exception as e:
            print(f"Failed to trigger n8n: {e}")
    return {"status": "Invites Queued"}

@app.get("/workspace", response_class=HTMLResponse)
async def workspace(request: Request):
    return templates.TemplateResponse("workspace.html", {"request": request})

@app.post("/upload-video")
async def upload_video_form(video_url: str = Form(...)):
    # Wrapper to handle form submission from dashboard
    # Triggers the Gemini process
    return {"status": "Processing Started", "url": video_url}
