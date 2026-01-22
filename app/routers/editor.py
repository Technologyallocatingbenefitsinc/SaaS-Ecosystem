from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import BaseModel
from fpdf import FPDF
import io
import google.generativeai as genai
from app.config import settings
from app.services.pptx_engine import generate_pptx, THEMES
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
    writing_style: str = "neutral"
    slide_count: int = 10
    html_content: str = None # Optional HTML from editor (with images)

# ...

@router.post("/export-slides-pdf")
async def generate_user_slides_pdf(
    request: PPTXRequest, 
    user = Depends(get_replit_user)
):
    try:
        # 1. Get Slides
        json_str = await convert_text_to_slides_json(
            request.text, 
            count=request.slide_count, 
            tone=request.writing_style,
            html_content=request.html_content
        )
        try:
            slide_data = json.loads(json_str)
        except:
             slide_data = [{"title": "Study Notes", "content": request.text}]

        # 2. Setup PDF (Landscape for 16:9, or Square)
        if request.aspect_ratio == "1:1":
            pdf = FPDF(orientation='P', unit='mm', format=(200, 200))
            width, height = 200, 200
        else:
            pdf = FPDF(orientation='L', unit='mm', format='A4')
            width, height = 297, 210

        # 3. Get Theme Colors
        theme = THEMES.get(request.theme, THEMES["default"])
        bg = theme["bg_color"]
        title_c = theme["title_color"]
        body_c = theme["body_color"]
        accent_c = theme["accent_color"]

        pdf.set_auto_page_break(auto=False)
        
        # Check Watermark Condition
        should_watermark = False
        if not user or (user.tier == "student" and user.credits <= 1):
             should_watermark = True

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
                # We need a custom color for this specific theme logic if it differs,
                # but PPTX used hardcoded RGB(253, 230, 138) for warm header.
                # Let's match that behavior.
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
            pdf.set_font("Helvetica", "B", 24) # Slightly smaller than 28 for better fit
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
            pdf.multi_cell(width-40, 12, slide.get("title", "Untitled"), align='L')
            
            # Content (Points)
            pdf.set_font("Helvetica", "", 16) # Adjusted 18 -> 16
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
                    pdf.multi_cell(width-(content_x*2), 9, f"-  {p}")
                    pdf.ln(2) 
            else:
                pdf.set_x(content_x)
                pdf.multi_cell(width-(content_x*2), 9, str(content_text))

            # --- Watermark (Per Slide) ---
            if should_watermark:
                pdf.set_xy(0, height - 15)
                pdf.set_font("Helvetica", "I", 12)
                # Use a subtle color, maybe gray or theme title color with opacity (FPDF doesn't do alpha easily)
                # Just use title color or gray
                pdf.set_text_color(128, 128, 128) 
                pdf.cell(width, 10, "Generated by MODYFIRE", align='C')

        pdf_bytes = pdf.output()
        
        return Response(
            content=bytes(pdf_bytes),
            headers={"Content-Disposition": "attachment; filename='study_slides.pdf'"},
            media_type="application/pdf"
        )

    except Exception as e:
        print(f"PDF Slides Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

