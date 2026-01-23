from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import BaseModel
from fpdf import FPDF
import io
import google.generativeai as genai
from app.config import settings
from app.services.pptx_engine import generate_pptx, THEMES
from app.services.pptx_engine import generate_pptx, THEMES
from app.services.gemini_engine import convert_text_to_slides_json, generate_quiz_from_text, generate_flashcards_from_text, identify_viral_clips
from app.routers.auth import get_replit_user
import json

router = APIRouter()

# Ensure genai is configured even if gemini_engine wasn't imported first
genai.configure(api_key=settings.GEMINI_API_KEY)

class RewriteRequest(BaseModel):
    text: str
    tone: str

class StudyRequest(BaseModel):
    text: str

class ClipsRequest(BaseModel):
    video_url: str

class PPTXRequest(BaseModel):
    text: str
    theme: str = "default"
    aspect_ratio: str = "16:9" # "16:9" or "1:1"
    writing_style: str = "neutral"
    slide_count: int = 10
    html_content: str = None # Optional HTML from editor (with images)

# ...

async def _generate_pdf_bytes(request: PPTXRequest, user) -> bytes:
    """Helper to generate PDF bytes from a request."""
    # 1. Get Slides
    json_str = await convert_text_to_slides_json(
        request.text, 
        count=request.slide_count, 
        tone=request.writing_style,
        html_content=request.html_content
    )
    try:
        slide_data = json.loads(json_str)
    except Exception as e:
         print(f"JSON Parse Error: {e} | Content: {json_str[:100]}...")
         # Fallback but warn
         slide_data = [{"title": "Error Parsing Slides", "content": "The AI response could not be parsed. Please try again or use simpler text."}]

    # 2. Setup PDF (Landscape for 16:9, or Square)
    if request.aspect_ratio == "1:1":
        pdf = FPDF(orientation='P', unit='mm', format=(200, 200))
        width, height = 200, 200
    else:
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        width, height = 297, 210
    
    pdf.set_compression(False)

    # 3. Get Theme Colors
    theme = THEMES.get(request.theme, THEMES["default"])
    bg = theme["bg_color"]
    title_c = theme["title_color"]
    body_c = theme["body_color"]
    accent_c = theme["accent_color"]

    # Register Custom Fonts
    try:
        pdf.add_font("Caveat", "", "app/static/fonts/Caveat-Regular.ttf", uni=True)
        pdf.add_font("Caveat", "B", "app/static/fonts/Caveat-Bold.ttf", uni=True)
    except Exception as e:
        print(f"Font loading warning: {e}")

    # Determine Font Family based on Theme
    font_family = "Helvetica"
    # Themes that use handwriting style
    if request.theme in ["fun", "warm", "sunset", "ocean"]:
        font_family = "Caveat"
    
    # Check Watermark Condition
    should_watermark = False
    if not user or (user.tier == "student" and user.credits <= 1):
            should_watermark = True

    # Helper to clean text for FPDF (Latin-1 only for standard fonts, UTF-8 for TTF)
    def _sanitize(text: str) -> str:
         # Replace common smart quotes/bullets first
        replacements = {
            "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
            "\u2013": "-", "\u2014": "-", "\u2022": "-", "\u2026": "..."
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        
        # If using standard Helvetica, we must strip to Latin-1
        if font_family == "Helvetica":
            return text.encode('latin-1', 'replace').decode('latin-1')
        # If using loaded TTF (Caveat), FPDF (uni=True) handles UTF-8 better, 
        # but we still want to avoid complex emojis that the font doesn't support.
        # However, FPDF2 might still prefer clean text. Let's keep strict for safety 
        # but maybe allow slightly more if we trusted the font (Caveat doesn't have emojis).
        # Safe bet: still strip to latin-1 or similar compatible range to prevent "character not in font" error
        return text.encode('latin-1', 'replace').decode('latin-1')

    for slide in slide_data:
        pdf.add_page()
        
        # Background
        pdf.set_fill_color(*bg)
        pdf.rect(0, 0, width, height, 'F')
        
        # --- Draw Theme Layout ---
        # Using FPDF shapes to match PPTX themes
        pdf.set_fill_color(*accent_c)
        
        if request.theme == "corporate":
            # Left Accent Bar (approx 12.7mm = 0.5 inch)
            pdf.rect(0, 0, 12.7, height, 'F')
            
        elif request.theme == "dark":
            # Top thin accent line (2.5mm approx 0.1 inch)
            pdf.rect(0, 0, width, 3, 'F')
            # Bottom right accent circle (approx 3 inches = 76mm)
            # FPDF ellipse: x, y, w, h
            pdf.ellipse(width - 50, height - 50, 75, 75, 'F')

        elif request.theme == "warm":
            # Soft top header block (approx 1.2 inches = 30mm)
            pdf.set_fill_color(253, 230, 138)
            pdf.rect(0, 0, width, 30, 'F')
            
        elif request.theme == "sunset":
            # Bottom accent bar (1 inch = 25.4mm)
            pdf.rect(0, height - 25, width, 25, 'F')
            
        elif request.theme == "forest":
            # Left sidebar thin (0.8 inch = 20mm)
            pdf.rect(0, 0, 20, height, 'F')
            
        elif request.theme == "ocean":
            # Top wave accent (0.5 inch = 12.7mm)
            pdf.rect(0, 0, width, 13, 'F')
            
        elif request.theme == "luxury":
            # Gold Frame (Top and Bottom 0.1 inch = 3mm)
            pdf.rect(0, 0, width, 3, 'F')
            pdf.rect(0, height - 3, width, 3, 'F')

        # Title
        # Adjust size for handwriting font (usually looks smaller)
        title_size = 28 if font_family == "Caveat" else 24
        pdf.set_font(font_family, "B", title_size) 
        pdf.set_text_color(*title_c)
        
        # Title Position Adjustment
        title_x, title_y = 20, 20
        if request.theme == "corporate":
            title_x = 25 # Shift for sidebar
        elif request.theme == "forest":
                title_x = 30 # Shift for sidebar
        elif request.theme == "warm":
            title_y = 10 # Adjust for header

        pdf.set_xy(title_x, title_y)
        pdf.multi_cell(width-40, 12, _sanitize(slide.get("title", "Untitled")), align='L')
        
        # Content (Points)
        body_size = 20 if font_family == "Caveat" else 16
        pdf.set_font(font_family, "", body_size) 
        pdf.set_text_color(*body_c)
        
        # Dynamic Y positioning
        current_y = pdf.get_y() + 10
        pdf.set_y(current_y)
        
        # Content X Position
        content_x = 25
        if request.theme == "corporate":
            content_x = 30
        elif request.theme == "forest":
            content_x = 35

        points = slide.get("points", [])
        content_text = slide.get("content", "")
        
        if points and isinstance(points, list):
            for p in points:
                pdf.set_x(content_x) 
                pdf.multi_cell(width-(content_x*2), 9, f"-  {_sanitize(p)}")
                pdf.ln(2) 
        else:
            pdf.set_x(content_x)
            pdf.multi_cell(width-(content_x*2), 9, _sanitize(str(content_text)))

        # --- Watermark (Per Slide) ---
        if should_watermark:
            pdf.set_xy(0, height - 15)
            pdf.set_font("Helvetica", "I", 12)
            pdf.set_text_color(128, 128, 128) 
            pdf.cell(width, 10, "Generated by MODYFIRE", align='C')

    return pdf.output()

class ReportRequest(BaseModel):
    text: str

@router.post("/export-pdf")
async def generate_text_report(request: ReportRequest):
    """
    Generates a standard A4 PDF report (not slides).
    """
    try:
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Header
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Study Course Summary", ln=True, align='C')
        pdf.ln(10)
        
        # Content
        pdf.set_font("Helvetica", "", 12)
        # Replace newlines to safe latin-1
        safe_text = request.text.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 10, safe_text)
        
        # Footer
        pdf.set_y(-15)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 10, "Generated by MODYFIRE", align='C')
        
        pdf_bytes = pdf.output()
        return Response(
            content=bytes(pdf_bytes),
            headers={"Content-Disposition": "attachment; filename='summary_report.pdf'"},
            media_type="application/pdf"
        )
    except Exception as e:
        print(f"Report PDF Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-slides-pdf")
async def generate_user_slides_pdf(
    request: PPTXRequest, 
    user = Depends(get_replit_user)
):
    try:
        pdf_bytes = await _generate_pdf_bytes(request, user)
        return Response(
            content=bytes(pdf_bytes),
            headers={"Content-Disposition": "attachment; filename='study_slides.pdf'"},
            media_type="application/pdf"
        )
    except Exception as e:
        print(f"PDF Slides Error: {e}")
        # Return 400 so client knows it's a request/generation issue
        raise HTTPException(status_code=400, detail=f"Generation failed: {str(e)}")

@router.post("/preview-pdf")
async def preview_user_slides_pdf(
    request: PPTXRequest,
    user = Depends(get_replit_user)
):
    try:
        pdf_bytes = await _generate_pdf_bytes(request, user)
        return Response(
            content=bytes(pdf_bytes),
            headers={"Content-Disposition": "inline; filename='preview.pdf'"}, 
            media_type="application/pdf"
        )
    except Exception as e:
        print(f"Preview Error: {e}")
        raise HTTPException(status_code=400, detail=f"Preview generation failed: {str(e)}")

@router.post("/export-pptx")
async def generate_user_pptx(
    request: PPTXRequest, 
    user = Depends(get_replit_user)
):
    try:
        # 1. Convert text to JSON Structure via Gemini
        json_str = await convert_text_to_slides_json(
            request.text, 
            count=request.slide_count, 
            tone=request.writing_style,
            html_content=request.html_content
        )
        
        # 2. Parse JSON
        try:
            slide_data = json.loads(json_str)
        except json.JSONDecodeError as je:
             print(f"JSON Decode Error during PPTX: {je}")
             # Return parsing error explicitly
             raise ValueError("AI response was not valid JSON.")
            
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
        raise HTTPException(status_code=400, detail=f"Export failed: {str(e)}")

@router.post("/rewrite")
async def rewrite_text(request: RewriteRequest):
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"Rewrite the following text to be {request.tone}. Keep the meaning the same but adjust the style.\n\nText: {request.text}"
        
        response = model.generate_content(prompt)
        return {"rewritten_text": response.text}
    except Exception as e:
        print(f"Rewrite Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-quiz")
async def create_quiz(request: StudyRequest):
    try:
        json_str = await generate_quiz_from_text(request.text)
        try:
            quiz_data = json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback for simple errors or re-try logic could happen here
             raise ValueError("AI failed to generate valid JSON for quiz.")
        
        return {"questions": quiz_data}
    except Exception as e:
        print(f"Quiz Gen Error: {e}")
        raise HTTPException(status_code=400, detail=f"Quiz generation failed: {str(e)}")

@router.post("/generate-flashcards")
async def create_flashcards(request: StudyRequest):
    try:
        json_str = await generate_flashcards_from_text(request.text)
        try:
             cards_data = json.loads(json_str)
        except json.JSONDecodeError:
             raise ValueError("AI failed to generate valid JSON for flashcards.")
             
        return {"flashcards": cards_data}
    except Exception as e:
        print(f"Flashcard Gen Error: {e}")
    except Exception as e:
        print(f"Flashcard Gen Error: {e}")
        raise HTTPException(status_code=400, detail=f"Flashcard generation failed: {str(e)}")

@router.post("/generate-clips")
async def create_viral_clips(request: ClipsRequest):
    try:
        # 1. Check if URL is present
        if not request.video_url:
             raise ValueError("Video URL is required for clip analysis")

        # 2. Call Engine
        json_str = await identify_viral_clips(request.video_url)
        
        # 3. Parse and Return
        try:
             clips_data = json.loads(json_str)
        except json.JSONDecodeError:
             raise ValueError("AI failed to generate valid JSON for clips.")
             
        return {"clips": clips_data}
    except Exception as e:
        print(f"Clip Gen Error: {e}")
        raise HTTPException(status_code=400, detail=f"Clip generation failed: {str(e)}")

from app.services.gemini_engine import generate_audio_script
from app.services.audio_engine import synthesize_podcast_audio

class AudioRequest(BaseModel):
    text: str # The transcript or notes

class ScriptRequest(BaseModel):
    script: list # The list of [{speaker, text}]

@router.post("/generate-audio-script")
async def create_audio_script(request: AudioRequest):
    try:
        json_str = await generate_audio_script(request.text)
        try:
             script_data = json.loads(json_str)
        except json.JSONDecodeError:
             raise ValueError("AI failed to generate valid JSON for script.")
        
        return {"script": script_data}
    except Exception as e:
        print(f"Audio Script Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/synthesize-audio")
async def create_audio_file(request: ScriptRequest):
    try:
        # Generate generic filename
        filename = f"podcast_{io.BytesIO().__hash__()}.mp3"
        filepath = f"user_uploads/{filename}"
        
        synthesize_podcast_audio(request.script, output_filename=filepath)
        
        return {"audio_url": f"/uploads/{filename}"}
    except Exception as e:
        print(f"Audio Synth Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from app.services.gemini_engine import chat_with_video

class ChatRequest(BaseModel):
    text: str # Transcript
    history: list = [] # List of {role, text}
    question: str

@router.post("/chat-video")
async def ask_video_question(request: ChatRequest):
    try:
        answer = await chat_with_video(request.text, request.history, request.question)
        return {"answer": answer}
    except Exception as e:
        print(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

