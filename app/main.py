from fastapi import FastAPI, Depends, HTTPException, Header, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from app.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
from app.database import engine, get_db, Base
from app.config import settings
from app.services.gemini_engine import process_video_content
from app.services.gemini_engine import process_video_content
from app.routers import auth, editor, legal, upload, analytics
from app.models import SlideDeck
from app.models import SlideDeck
import httpx

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables (if simplified flow)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "*.replit.app", "*.replit.dev"]
)

# Mount Static & Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="user_uploads"), name="uploads")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(editor.router, prefix="/editor", tags=["editor"])
app.include_router(legal.router, prefix="/legal", tags=["legal"])
app.include_router(legal.router, prefix="/legal", tags=["legal"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(analytics.router, prefix="/api", tags=["analytics"])
from app.routers import dashboard
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {"user": None})

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
    user_id: int = 1, # Default to 1 for system tests
    user_tier: str = "student",
    slide_count: str = "6-10",
    x_n8n_auth: str = Header(None),
    db = Depends(get_db)
):
    if x_n8n_auth != settings.AUTH_SECRET_TOKEN:
         raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        result = await process_video_content(video_url, user_tier, user_id, slide_count)
        return result
    except Exception as e:
        print(f"Error processing video: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, tier: str = None, user = Depends(auth.get_replit_user)):
    # Fallback/Default tier logic
    # 1. Check Query Param (Preview Mode)
    # 2. Check Auth User
    # 3. Default to Professor
    user_tier = tier or (user.tier if user else "professor")
    
    mock_stats = {
        "credits": user.credits if user else 25,
        "tier": user_tier
    }
    
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user,
        "tier": user_tier,
        "credits": mock_stats["credits"]
    })

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, user = Depends(auth.get_replit_user)):
    if not user:
        return RedirectResponse(url="/dashboard") # Or Login
    return templates.TemplateResponse(request, "profile.html", {"user": user})

@app.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request, user = Depends(auth.get_replit_user)):
    return templates.TemplateResponse(request, "billing.html", {"user": user})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request, user = Depends(auth.get_replit_user)):
    return templates.TemplateResponse(request, "privacy.html", {"user": user})

@app.get("/tos", response_class=HTMLResponse)
async def tos_page(request: Request):
    return templates.TemplateResponse(request, "tos.html", {})

@app.get("/trust-center", response_class=HTMLResponse)
async def trust_center_page(request: Request):
    return templates.TemplateResponse(request, "trust-center.html", {})

@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    return templates.TemplateResponse(request, "reset_password.html", {})

@app.post("/invite-students")
async def invite_students(user = Depends(auth.get_replit_user), db = Depends(get_db)):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Generate Class Code if missing
    import random, string
    code = user.my_class_code
    if not code:
        code = "CLASS-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        user.my_class_code = code
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    # In production: Trigger n8n email loop here
    print(f"Invite Code Generated: {code}")
    
    return {"status": "success", "class_code": code}

@app.post("/join-class")
async def join_class(
    request: Request, 
    user = Depends(auth.get_replit_user), 
    db = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    data = await request.json()
    code = data.get("code")
    
    if not code:
        raise HTTPException(status_code=400, detail="Class code required")
        
    # Find Professor with this code
    from sqlalchemy import select
    res = await db.execute(select(User).where(User.my_class_code == code))
    professor = res.scalars().first()
    
    if not professor:
        raise HTTPException(status_code=404, detail="Invalid Class Code")
        
    user.joined_class_code = code
    db.add(user)
    await db.commit()
    
    return {"status": "success", "message": f"Successfully joined {professor.username}'s class!"}

@app.get("/workspace", response_class=HTMLResponse)
async def workspace(request: Request):
    return templates.TemplateResponse(request, "workspace.html")

from app.models import SlideDeck, User # Ensure imports

@app.post("/upload-video")
async def upload_video_form(
    video_url: str = Form(...), 
    slide_count: str = Form("6-10"), 
    user = Depends(auth.get_replit_user),
    db = Depends(get_db)
):
    user_tier = user.tier if user else "student"
    # Fallback to system user 1 if not logged in (for demo/onboarding)
    user_id = user.id if user else 1 
    
    try:
        result = await process_video_content(video_url, user_tier, user_id, slide_count)
        
        # Save to DB for Recent Activity (Only if authenticated)
        if user:
            new_deck = SlideDeck(
                user_id=user.id,
                video_url=video_url,
                summary_content=result.get("content", ""),
                # pdf_path could be generated later or null
            )
            db.add(new_deck)
            await db.commit()
            await db.refresh(new_deck)
        
        return result
    except Exception as e:
        print(f"Error processing video: {e}")
        return {"status": "Error", "message": str(e)}
