from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import BaseModel
from fpdf import FPDF
import io
import google.generativeai as genai
from app.config import settings
from app.services.pptx_engine import generate_pptx
from app.services.gemini_engine import convert_text_to_slides_json
from app.routers.auth import get_replit_user
import json

router = APIRouter()

class RewriteRequest(BaseModel):
    text: str
    tone: str

class PPTXRequest(BaseModel):
    text: str
    theme: str = "default"
    aspect_ratio: str = "16:9" # "16:9" or "1:1"

# ...

@router.post("/export-pptx")
async def generate_user_pptx(
    request: PPTXRequest, 
    user = Depends(get_replit_user)
):
    try:
        # 1. Convert text to JSON Structure via Gemini
        json_str = await convert_text_to_slides_json(request.text, count=10)
        
        # 2. Parse JSON
        try:
            slide_data = json.loads(json_str)
        except json.JSONDecodeError:
            slide_data = [{"title": "Study Notes", "content": request.text}]
            
        # 3. Check Watermark Condition
        should_watermark = False
        if not user or (user.tier == "student" and user.credits <= 1):
            should_watermark = True

        # 4. Generate PPTX
        pptx_bytes = generate_pptx(
            slide_data, 
            watermark=should_watermark, 
            theme_name=request.theme,
            aspect_ratio=request.aspect_ratio
        )
        
        return Response(
            content=pptx_bytes,
            headers={"Content-Disposition": "attachment; filename='study_notes.pptx'"},
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    except Exception as e:
        print(f"PPTX Gen Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rewrite")
async def rewrite_text(request: RewriteRequest):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = f"Rewrite the following text to be {request.tone}. Keep the meaning the same but adjust the style.\n\nText: {request.text}"
        
        response = model.generate_content(prompt)
        return {"rewritten_text": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

