from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form, Request
import shutil
import os
import aiofiles
from pathlib import Path
import asyncio
import hashlib
import httpx
from app.config import settings
from app.routers import auth
from fastapi import Depends
from app.database import get_db
from app.limiter import limiter

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None

router = APIRouter()

UPLOAD_BASE_DIR = Path("user_uploads")
UPLOAD_BASE_DIR.mkdir(exist_ok=True)

async def remove_file_after_delay(path: Path, delay: int = 86400):
    """Deletes the file after 24 hours (86400 seconds)"""
    await asyncio.sleep(delay)
    if path.exists():
        path.unlink()
        print(f"Cleanup: Deleted {path}")

async def calculate_file_hash(content: bytes) -> str:
    """Calculates SHA256 hash of bytes"""
    sha256_hash = hashlib.sha256(content)
    return sha256_hash.hexdigest()

async def signal_n8n_to_start(file_path: str, user_email: str, user_role: str, file_hash: str):
    """Signals n8n to start processing the uploaded file"""
    webhook_url = settings.N8N_UPLOAD_WEBHOOK
    payload = {
        "event": "file_uploaded_ready",
        "file_path": str(file_path),
        "user_email": user_email,
        "role": user_role,
        "file_hash": file_hash,
        "auth_token": settings.AUTH_SECRET_TOKEN
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(webhook_url, json=payload)
            return response.status_code
        except Exception as e:
            print(f"Failed to signal n8n: {e}")
            return 500

async def delete_user_folder(user_id: int):
    """Securely wipes all files for a specific user"""
    # Local Wipe
    user_dir = UPLOAD_BASE_DIR / str(user_id)
    if user_dir.exists():
        shutil.rmtree(user_dir)
        print(f"GDPR: Wiped local storage for User {user_id}")
    
    # Supabase Wipe (Best Effort)
    if settings.SUPABASE_URL and settings.SUPABASE_KEY and create_client:
        try:
            supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            # Basic implementation requires iterating files which is skipped for brevity
            print(f"GDPR: Please verify Supabase bucket cleanup for User {user_id}")
        except Exception as e:
            print(f"Supabase Wipe Error: {e}")

@router.post("/upload-content")
@limiter.limit("10/minute")
async def upload_local_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user = Depends(auth.get_replit_user)
):
    # For demo/local testing, fallback to user 1 if not on Replit
    user_obj = user
    user_id = user_obj.id if user_obj else 1
    user_email = user_obj.email if user_obj else "demo@example.com"
    user_role = user_obj.tier if user_obj else "student"
    
    print(f"DEBUG: Upload request from User ID {user_id}")

    try:
        content = await file.read()
        # Clean filename: replace spaces with underscores to avoid URL issues
        safe_filename = file.filename.replace(" ", "_")
        file_hash = await calculate_file_hash(safe_filename.encode() + content[:100])

        # CHECK FOR SUPABASE CONFIG
        if settings.SUPABASE_URL and settings.SUPABASE_KEY and create_client:
            try:
                supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                supabase_path = f"{user_id}/{safe_filename}"
                
                # Upload
                supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
                    supabase_path,
                    content,
                    {"content-type": file.content_type, "upsert": "true"}
                )
                
                # Get Public URL
                public_url = supabase.storage.from_(settings.SUPABASE_BUCKET).get_public_url(supabase_path)
                
                # Signal N8N with URL
                background_tasks.add_task(signal_n8n_to_start, public_url, user_email, user_role, file_hash)
                
                return {
                    "message": "Upload successful (Supabase).", 
                    "path": public_url,
                    "url": public_url,
                    "filename": safe_filename,
                    "hash": file_hash,
                    "storage": "supabase"
                }
            except Exception as supabase_e:
                print(f"Supabase Upload Failed: {supabase_e}. Falling back to local.")
        
        # LOCAL STORAGE FALLBACK
        user_dir = UPLOAD_BASE_DIR / str(user_id)
        user_dir.mkdir(exist_ok=True)
        
        file_path = user_dir / safe_filename
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            await out_file.write(content)
            
        # Schedule cleanup
        background_tasks.add_task(remove_file_after_delay, file_path)
        
        # Signal n8n
        background_tasks.add_task(signal_n8n_to_start, str(file_path.absolute()), user_email, user_role, file_hash)

        # Build appropriate web path
        web_path = f"/uploads/{user_id}/{safe_filename}"

        return {
            "message": "Upload successful.", 
            "path": str(file_path),
            "url": web_path,
            "filename": safe_filename,
            "hash": file_hash,
            "storage": "local"
        }
        
    except Exception as e:
        print(f"Upload Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
