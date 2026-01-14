import google.generativeai as genai
from app.config import settings
from youtube_transcript_api import YouTubeTranscriptApi

genai.configure(api_key=settings.GEMINI_API_KEY)

def get_transcript(video_url: str):
    try:
        video_id = video_url.split("v=")[1]
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([i['text'] for i in transcript_list])
        return transcript_text
    except Exception as e:
        raise Exception(f"Failed to fetch transcript: {str(e)}")

async def process_video_content(video_url: str, user_tier: str):
    transcript = get_transcript(video_url)
    
    if user_tier == "student":
        model_name = "gemini-1.5-flash"
        prompt = f"Summarize the following video transcript into concise bullet points suitable for study notes:\n\n{transcript}"
    elif user_tier == "professor":
        model_name = "gemini-1.5-pro" # Using 1.5 Pro as proxy for 3.0 Pro
        prompt = f"Create a detailed academic study guide with citations based on the following transcript:\n\n{transcript}"
    elif user_tier == "podcaster":
        model_name = "gemini-1.5-pro"
        prompt = f"Generate slide descriptions and visual imagery ideas for a presentation based on this transcript. For each slide, provide the text content and a prompt for an image generator:\n\n{transcript}"
    else:
        model_name = "gemini-1.5-flash"
        prompt = f"Summarize this:\n\n{transcript}"

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    
    return {
        "tier": user_tier,
        "model": model_name,
        "content": response.text
    }
