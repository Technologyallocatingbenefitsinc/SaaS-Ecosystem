import google.generativeai as genai
from app.config import settings
from youtube_transcript_api import YouTubeTranscriptApi

genai.configure(api_key=settings.GEMINI_API_KEY)

def extract_video_id(video_url: str) -> str:
    import re
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, video_url)
        if match:
             return match.group(1)
    raise Exception(f"Could not extract video ID from URL: {video_url}")

def get_transcript(video_url: str):
    try:
        video_id = extract_video_id(video_url)
        # Use the newer list_transcripts API (better for multiple languages/auto-gen)
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to find a manually created english transcript, or auto-generated one
        # Prefer manually created English, then auto-generated English
        try:
            transcript = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
        except:
             try:
                 transcript = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
             except:
                 # Last resort: just get the first available one (even if not English, better than crash?)
                 # Or stick to English requirement.
                 # Let's try flexible search
                 transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                 
        transcript_list = transcript.fetch()

        transcript_text = " ".join([i['text'] for i in transcript_list])
        return transcript_text
    except Exception as e:
        raise Exception(f"Failed to fetch transcript: {str(e)}")

from app.services.usage_logger import log_token_usage

async def process_video_content(video_url: str, user_tier: str, user_id: int, slide_count: str = "6-10"):
    transcript = get_transcript(video_url)
    
    if user_tier == "student":
        model_name = "gemini-2.5-flash"
        prompt = f"Summarize the following video transcript into concise bullet points suitable for study notes. Target length: {slide_count} slides/sections.\\n\\n{transcript}"
    elif user_tier == "professor":
        model_name = "gemini-2.5-flash" 
        prompt = f"Create a detailed academic study guide with citations based on the following transcript. Structure the guide into {slide_count} distinct chapters or modules.\\n\\n{transcript}"
    elif user_tier == "podcaster":
        model_name = "gemini-2.5-flash"
        prompt = f"Generate slide descriptions and visual imagery ideas for a presentation based on this transcript. PRODUCE EXACTLY {slide_count} SLIDES. For each slide, provide the text content and a prompt for an image generator:\\n\\n{transcript}"
    else:
        model_name = "gemini-2.5-flash"
        prompt = f"Summarize this:\\n\\n{transcript}"

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    
    # 🕵️ Log usage for budget tracking
    try:
        usage = response.usage_metadata
        await log_token_usage(
            user_id=user_id,
            plan_type=user_tier,
            prompt_tokens=usage.prompt_token_count,
            response_tokens=usage.candidates_token_count
        )
    except Exception as e:
        print(f"Usage logging failed: {e}")
        
    return {
        "tier": user_tier,
        "model": model_name,
        "content": response.text
    }

async def convert_text_to_slides_json(text: str, count: int = 10):
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Convert the following study notes into a JSON structure for a PowerPoint presentation.
    Create exactly {count} slides.
    Output must be a plain JSON list of objects. Each object must have:
    - "title": string
    - "content": string (bullet points separated by newlines)
    
    Text:
    {text}
    """
    response = model.generate_content(prompt)
    
    # Clean markdown if present
    cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
    return cleaned_text
