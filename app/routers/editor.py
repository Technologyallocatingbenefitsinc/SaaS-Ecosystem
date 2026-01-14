from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from fpdf import FPDF
import io
import google.generativeai as genai
from app.config import settings

router = APIRouter()

class RewriteRequest(BaseModel):
    text: str
    tone: str

class PDFRequest(BaseModel):
    text: str

def create_pdf(text_content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    # multi_cell handles line breaks automatically
    pdf.multi_cell(0, 10, txt=text_content)
    # Output to string/bytes
    return pdf.output()

@router.post("/export-pdf")
async def generate_user_pdf(request: PDFRequest):
    try:
        # FPDF2 output() returns bytes directly in recent versions or can write to string
        # We'll stick to the bytearray approach compatible with FastAPI responses
        pdf_bytes = create_pdf(request.text)
        
        return Response(
            content=bytes(pdf_bytes),
            headers={"Content-Disposition": "attachment; filename='summary.pdf'"},
            media_type="application/pdf"
        )
    except Exception as e:
        print(f"PDF Gen Error: {e}")
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

