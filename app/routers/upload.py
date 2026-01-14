from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import shutil
import os
import aiofiles
from pathlib import Path
import asyncio

router = APIRouter()

UPLOAD_DIR = Path("user_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

async def remove_file_after_delay(path: Path, delay: int = 86400):
    """Deletes the file after 24 hours (86400 seconds)"""
    await asyncio.sleep(delay)
    if path.exists():
        path.unlink()
        print(f"Cleanup: Deleted {path}")

@router.post("/upload-content")
async def upload_local_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    try:
        # File Size check could be done via reading chunks, but for MVP we rely on SpooledTemporaryFile behavior
        # In production, we'd check Content-Length header or stream and count bytes
        
        file_path = UPLOAD_DIR / file.filename
        
        # Async write
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read() # Warning: This loads file into RAM if not careful, but UploadFile spools
            await out_file.write(content)
            
        # Schedule cleanup
        background_tasks.add_task(remove_file_after_delay, file_path)
        
        # Trigger Processing (Placeholder for now, would call Gemini Service)
        # await process_local_file(file_path)

        return {
            "message": "Upload successful", 
            "path": str(file_path),
            "filename": file.filename
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
