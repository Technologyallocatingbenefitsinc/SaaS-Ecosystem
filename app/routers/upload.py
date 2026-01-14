from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form
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

router = APIRouter()

UPLOAD_BASE_DIR = Path("user_uploads")
UPLOAD_BASE_DIR.mkdir(exist_ok=True)

async def remove_file_after_delay(path: Path, delay: int = 86400):
    """Deletes the file after 24 hours (86400 seconds)"""
    await asyncio.sleep(delay)
    if path.exists():
        path.unlink()
        print(f"Cleanup: Deleted {path}")

async def calculate_file_hash(file_path: Path) -> str:
    """Calculates SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    async with aiofiles.open(file_path, "rb") as f:
        while True:
            chunk = await f.read(4096)
            if not chunk:
                break
            sha256_hash.update(chunk)
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
    user_dir = UPLOAD_BASE_DIR / str(user_id)
    if user_dir.exists():
        shutil.rmtree(user_dir)
        print(f"GDPR: Wiped storage for User {user_id}")

@router.post("/upload-content")
async def upload_local_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user = Depends(auth.get_replit_user)
):
    if not user:
         raise HTTPException(status_code=401, detail="Please sign in via Replit Auth to upload files.")
    
    try:
        user_id = user.id 
        user_email = user.email
        user_role = user.tier

        # Create user-specific directory
        user_dir = UPLOAD_BASE_DIR / str(user_id)
        user_dir.mkdir(exist_ok=True)
        
        file_path = user_dir / file.filename
        
        # Async write
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read() 
            await out_file.write(content)
            
        # Calculate Hash
        file_hash = await calculate_file_hash(file_path)

        # Schedule cleanup
        background_tasks.add_task(remove_file_after_delay, file_path)
        
        # Signal n8n
        background_tasks.add_task(signal_n8n_to_start, str(file_path.absolute()), user_email, user_role, file_hash)

        return {
            "message": "Upload successful. Processing started.", 
            "path": str(file_path),
            "filename": file.filename,
            "hash": file_hash
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
