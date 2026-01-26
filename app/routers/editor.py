from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import BaseModel
from fpdf import FPDF
import io
import os
import google.generativeai as genai
from app.config import settings
from app.services.pptx_engine import generate_pptx, THEMES
from app.services.gemini_engine import (
    convert_text_to_slides_json, 
    generate_quiz_from_text, 
    generate_flashcards_from_text, 
    identify_viral_clips,
    generate_audio_script,
    chat_with_video,
    generate_blog_from_text,
    generate_carousel_from_text
)
from app.services.audio_engine import synthesize_podcast_audio
from app.routers.auth import get_replit_user
import json
import uuid

router = APIRouter()

genai.configure(api_key=settings.GEMINI_API_KEY)

class RewriteRequest(BaseModel):
    text: str
    tone: str

class StudyRequest(BaseModel):
    text: str
    language: str = "English"

class ClipsRequest(BaseModel):
    video_url: str

class PPTXRequest(BaseModel):
    text: str
    theme: str = "default"
    aspect_ratio: str = "16:9" 
    writing_style: str = "neutral"
    slide_count: int = 10
    html_content: str = None 
    language: str = "English"

class ReportRequest(BaseModel):
    text: str

class AudioRequest(BaseModel):
    text: str 
    language: str = "English"

class ScriptRequest(BaseModel):
    script: list 

class ChatRequest(BaseModel):
    text: str 
    history: list = [] 
    question: str

async def _generate_pdf_bytes(request: PPTXRequest, user) -> bytes:
    json_str = await convert_text_to_slides_json(
        request.text, 
        count=request.slide_count, 
        tone=request.writing_style,
        html_content=request.html_content,
        language=request.language
    )

    try:
        slide_data = json.loads(json_str)
    except Exception as e:
         print(f"JSON Parse Error: {e} | Content: {json_str[:100]}...")
         slide_data = [{"title": "Error Parsing Slides", "content": "The AI response could not be parsed."}]

    if request.aspect_ratio == "1:1":
        pdf = FPDF(orientation='P', unit='mm', format=(200, 200))
        width, height = 200, 200
    else:
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        width, height = 297, 210
    
    pdf.set_compression(False)
    theme = THEMES.get(request.theme, THEMES["default"])
    bg, title_c, body_c, accent_c = theme["bg_color"], theme["title_color"], theme["body_color"], theme["accent_color"]

    try:
        pdf.add_font("Caveat", "", "app/static/fonts/Caveat-Regular.ttf", uni=True)
        pdf.add_font("Caveat", "B", "app/static/fonts/Caveat-Bold.ttf", uni=True)
    except Exception as e:
        print(f"Font loading warning: {e}")

    font_family = "Caveat" if request.theme in ["fun", "warm", "sunset", "ocean"] else "Helvetica"
    should_watermark = not user or (user.tier == "student" and user.credits <= 1)

    def _sanitize(text: str) -> str:
        replacements = {"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'", "\u2013": "-", "\u2014": "-", "\u2022": "-", "\u2026": "..."}
        for k, v in replacements.items(): text = text.replace(k, v)
        return text.encode('latin-1', 'replace').decode('latin-1')

    for slide in slide_data:
        pdf.add_page()
        pdf.set_fill_color(*bg)
        pdf.rect(0, 0, width, height, 'F')
        pdf.set_fill_color(*accent_c)
        
        if request.theme == "corporate": pdf.rect(0, 0, 12.7, height, 'F')
        elif request.theme == "dark":
            pdf.rect(0, 0, width, 3, 'F')
            pdf.ellipse(width - 50, height - 50, 75, 75, 'F')
        elif request.theme == "warm":
            pdf.set_fill_color(253, 230, 138)
            pdf.rect(0, 0, width, 30, 'F')
        elif request.theme == "sunset": pdf.rect(0, height - 25, width, 25, 'F')
        elif request.theme == "forest": pdf.rect(0, 0, 20, height, 'F')
        elif request.theme == "ocean": pdf.rect(0, 0, width, 13, 'F')
        elif request.theme == "luxury":
            pdf.rect(0, 0, width, 3, 'F')
            pdf.rect(0, height - 3, width, 3, 'F')

        pdf.set_font(font_family, "B", 28 if font_family == "Caveat" else 24) 
        pdf.set_text_color(*title_c)
        title_x, title_y = 20, 20
        if request.theme == "corporate": title_x = 25
        elif request.theme == "forest": title_x = 30
        elif request.theme == "warm": title_y = 10

        pdf.set_xy(title_x, title_y)
        pdf.multi_cell(width-40, 12, _sanitize(slide.get("title", "Untitled")), align='L')
        
        pdf.set_font(font_family, "", 20 if font_family == "Caveat" else 16) 
        pdf.set_text_color(*body_c)
        pdf.set_y(pdf.get_y() + 10)
        
        content_x = 25
        if request.theme == "corporate": content_x = 30
        elif request.theme == "forest": content_x = 35

        points = slide.get("points", [])
        if points and isinstance(points, list):
            for p in points:
                pdf.set_x(content_x) 
                pdf.multi_cell(width-(content_x*2), 9, f"-  {_sanitize(p)}")
                pdf.ln(2) 
        else:
            pdf.set_x(content_x)
            pdf.multi_cell(width-(content_x*2), 9, _sanitize(str(slide.get("content", ""))))

        if should_watermark:
            pdf.set_xy(0, height - 15)
            pdf.set_font("Helvetica", "I", 12)
            pdf.set_text_color(128, 128, 128) 
            pdf.cell(width, 10, "Generated by MODYFIRE", align='C')

    return pdf.output()

@router.post("/export-pdf")
async def generate_text_report(request: ReportRequest):
    try:
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Study Course Summary", ln=True, align='C')
        pdf.ln(10)
        pdf.set_font("Helvetica", "", 12)
        safe_text = request.text.replace('**', '').replace('##', '')
        replacements = {"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'", "\u2013": "-", "\u2014": "-", "\u2022": "-", "\u2026": "..."}
        for k, v in replacements.items(): safe_text = safe_text.replace(k, v)
        safe_text = safe_text.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 10, safe_text)
        pdf.set_y(-15)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 10, "Generated by MODYFIRE", align='C')
        return Response(content=bytes(pdf.output()), headers={"Content-Disposition": "attachment; filename='summary_report.pdf'"}, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export-slides-pdf")
async def generate_user_slides_pdf(request: PPTXRequest, user = Depends(get_replit_user)):
    try:
        pdf_bytes = await _generate_pdf_bytes(request, user)
        return Response(content=bytes(pdf_bytes), headers={"Content-Disposition": "attachment; filename='study_slides.pdf'"}, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/preview-pdf")
async def preview_user_slides_pdf(request: PPTXRequest, user = Depends(get_replit_user)):
    try:
        pdf_bytes = await _generate_pdf_bytes(request, user)
        return Response(content=bytes(pdf_bytes), headers={"Content-Disposition": "inline; filename='preview.pdf'"}, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/export-pptx")
async def generate_user_pptx(request: PPTXRequest, user = Depends(get_replit_user)):
    try:
        json_str = await convert_text_to_slides_json(request.text, count=request.slide_count, tone=request.writing_style, html_content=request.html_content, language=request.language)
        slide_data = json.loads(json_str)
        pptx_bytes = generate_pptx(slide_data, watermark=(not user or (user.tier == "student" and user.credits <= 1)), theme_name=request.theme, aspect_ratio=request.aspect_ratio)
        return Response(content=pptx_bytes, headers={"Content-Disposition": "attachment; filename='study_notes.pptx'"}, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/rewrite")
async def rewrite_text(request: RewriteRequest):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = f"Rewrite the following text to be {request.tone}. Text: {request.text}"
        response = model.generate_content(prompt)
        return {"rewritten_text": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-quiz")
async def create_quiz(request: StudyRequest):
    try:
        json_str = await generate_quiz_from_text(request.text, language=request.language)
        return {"questions": json.loads(json_str)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/generate-flashcards")
async def create_flashcards(request: StudyRequest):
    try:
        json_str = await generate_flashcards_from_text(request.text, language=request.language)
        return {"flashcards": json.loads(json_str)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/generate-clips")
async def create_viral_clips(request: ClipsRequest):
    try:
        json_str = await identify_viral_clips(request.video_url)
        return {"clips": json.loads(json_str)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/generate-audio-script")
async def create_audio_script(request: AudioRequest):
    try:
        json_str = await generate_audio_script(request.text, language=request.language)
        return {"script": json.loads(json_str)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/synthesize-audio")
async def create_audio_file(request: ScriptRequest):
    try:
        filename = f"podcast_{uuid.uuid4().hex}.mp3"
        os.makedirs("user_uploads", exist_ok=True)
        abs_path = os.path.abspath(f"user_uploads/{filename}")
        synthesize_podcast_audio(request.script, output_filename=abs_path)
        return {"audio_url": f"/uploads/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat-video")
async def ask_video_question(request: ChatRequest):
    try:
        answer = await chat_with_video(request.text, request.history, request.question)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-blog")
async def create_blog(request: StudyRequest):
    try:
        blog_text = await generate_blog_from_text(request.text, language=request.language)
        return {"blog": blog_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-carousel")
async def create_carousel(request: StudyRequest):
    try:
        carousel_text = await generate_carousel_from_text(request.text, language=request.language)
        return {"carousel": carousel_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
