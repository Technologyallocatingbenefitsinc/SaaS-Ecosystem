import google.generativeai as genai
import markdown
from app.config import settings
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

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
    raise ValueError(f"Invalid YouTube URL: {video_url}")

def get_transcript(video_url: str, return_timestamps=False):
    try:
        video_id = extract_video_id(video_url)
        try:
            # 1. Try listing available transcripts
            try:
                # Environment specific: v1.2.3 uses instance method .list()
                api = YouTubeTranscriptApi()
                try:
                    transcript_list = api.list(video_id)
                except AttributeError:
                     # Standard API: static method .list_transcripts()
                     transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            except Exception as e:
                print(f"List Transcripts failed: {e}")
                # Try fallback static method if instance failed completely (e.g. init error)
                try:
                     transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                except:
                     raise e

            # 2. Try English (Manual or Generated)
            transcript = None
            try:
                transcript = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
            except:
                try:
                    transcript = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
                except:
                    # 3. Fallback: Take ANY available transcript
                    try:
                        transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB']) # Redundant retry?
                    except:
                        # Just grab the first one we can find?
                        for t in transcript_list:
                            transcript = t
                            break
            
            if not transcript:
                 raise NoTranscriptFound(video_id)

            transcript_data = transcript.fetch()
        
        except TranscriptsDisabled:
            raise ValueError("Subtitles are disabled for this video. Cannot generate summary.")
        except NoTranscriptFound:
            raise ValueError("No suitable English subtitles found for this video. Cannot generate summary.")
        except Exception as e:
            # Check for age restriction or cookies
            if "Sign in" in str(e) or "cookies" in str(e):
                 raise ValueError("This video is age-restricted or requires sign-in. Cannot access content.")
            raise e
        
        # If raw timestamps requested, return the list of dicts directly
        if return_timestamps:
            return transcript_data

        # Handle both dictionary (standard) and object (some versions) returns
        text_parts = []
        for item in transcript_data:
            if isinstance(item, dict):
                text_parts.append(item['text'])
            else:
                text_parts.append(getattr(item, 'text', str(item)))
                
        transcript_text = " ".join(text_parts)
        return transcript_text
    except ValueError as ve:
        raise ve # Pass through friendly errors
    except Exception as e:
        print(f"Transcript Error: {e}")
        raise ValueError(f"Failed to fetch transcript. The video might be private or unavailable. ({str(e)})")

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
        "content": markdown.markdown(response.text)
    }

async def convert_text_to_slides_json(text: str, count: int = 10, tone: str = "neutral", html_content: str = None):
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    # Use HTML content if valid, otherwise fallback to text
    content_to_process = html_content if html_content and len(html_content) > 50 else text

    prompt = f"""
    Convert the following content into a JSON structure for a PowerPoint presentation.
    Create exactly {count} slides. Use a {tone} tone/style for the content.
    
    IMPORTANT: The content may contain HTML <img> tags. If you find an image that is relevant to a specific slide's topic, extract its 'src' attribute and include it in the "image_url" field for that slide.
    
    Output must be a plain JSON list of objects. Each object must have:
    - "title": string
    - "points": list of strings (each string is a bullet point)
    - "notes": string (speaker notes for the slide)
    - "image_url": string (optional, the src URL of the image if one belongs on this slide)
    
    Ensure the JSON is valid and properly formatted. Do not include markdown code blocks.
    
    Content:
    {content_to_process}
    """
    response = model.generate_content(prompt)
    
    # Clean markdown if present
    cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
    return cleaned_text

async def generate_quiz_from_text(text: str):
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Create a multiple-choice quiz based on the following text.
    Generate 5 to 10 questions.
    
    Output strictly as a JSON list of objects:
    [
      {{
        "question": "Question text?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "answer": "Option B"
      }}
    ]
    
    Text:
    {text}
    """
    response = model.generate_content(prompt)
    cleaned = response.text.replace("```json", "").replace("```", "").strip()
    return cleaned

async def generate_flashcards_from_text(text: str):
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Create a set of flashcards based on the key concepts in the following text.
    Generate 5 to 15 cards.
    
    Output strictly as a JSON list of objects:
    [
      {{
        "front": "Term or Concept",
        "back": "Definition or Explanation"
      }}
    ]
    
    Text:
    {text}
    """
    response = model.generate_content(prompt)
    cleaned = response.text.replace("```json", "").replace("```", "").strip()
    cleaned = response.text.replace("```json", "").replace("```", "").strip()
    return cleaned

async def identify_viral_clips(video_url: str):
    # 1. Fetch transcript with timestamps
    transcript_data = get_transcript(video_url, return_timestamps=True)
    
    # Check if we got list of dicts or objects. Ensure list of dicts for generic use
    cleaned_transcript = []
    for item in transcript_data:
        if isinstance(item, dict):
            cleaned_transcript.append(item)
        else:
            # Convert object to dict if needed (fallback)
            cleaned_transcript.append({
                "text": getattr(item, 'text', ""),
                "start": getattr(item, 'start', 0),
                "duration": getattr(item, 'duration', 0)
            })

    # Limit transcript size for prompt context window if needed, but for now send all
    # To save tokens, we might format it compactly
    transcript_str = str(cleaned_transcript[:1000]) # send first 1000 chunks ~ maybe 10-15 mins?
    if len(cleaned_transcript) > 1000:
        transcript_str += "... (continues)"

    model = genai.GenerativeModel("gemini-2.0-flash-thinking-exp-01-21")
    prompt = f"""
    Analyze the following transcript data (list of {{text, start, duration}}).
    Identify 3-5 distinct segments (30-90 seconds long) that are most likely to go viral on TikTok/Shorts.
    Look for: High energy, strong hooks, controversial statements, or "aha" moments.

    Output strictly as a JSON list of objects:
    [
      {{
        "start_time": 120.5,
        "end_time": 165.0,
        "viral_score": 95,
        "reason": "Strong emotional hook about failure.",
        "suggested_caption": "Wait for the end... 🤯 #motivation"
      }}
    ]

    Transcript Data:
    {transcript_str}
    """
    
    response = model.generate_content(prompt)
    cleaned = response.text.replace("```json", "").replace("```", "").strip()
    return cleaned

async def generate_audio_script(transcript_text: str):
    model = genai.GenerativeModel("gemini-2.0-flash-thinking-exp-01-21")
    prompt = f"""
    Convert the following transcript into a natural, engaging podcast dialogue between two hosts:
    
    1. **Alex (The Host)**: Curious, enthusiastic, asks clarifying questions, uses analogies.
    2. **Sam (The Expert)**: Knowledgeable, calm, explains concepts clearly but not dryly.
    
    The dialogue should be about 3-5 minutes of reading time (approx 600-800 words).
    Focus on the core insights. Use "Um", "Exactly", "Right?" to make it sound natural.
    
    Output strictly as a JSON list of objects:
    [
      {{ "speaker": "Alex", "text": "Welcome back! Today we're diving into..." }},
      {{ "speaker": "Sam", "text": "It's a fascinating topic, Alex. Essentially..." }}
    ]
    
    Transcript:
    {transcript_text[:15000]} 
    """
    
    response = model.generate_content(prompt)
    cleaned = response.text.replace("```json", "").replace("```", "").strip()
    response = model.generate_content(prompt)
    cleaned = response.text.replace("```json", "").replace("```", "").strip()
    return cleaned

async def chat_with_video(transcript_text: str, history: list, question: str):
    """
    Answers a question based strictly on the transcript context.
    History is a list of {"role": "user"|"model", "text": "..."}
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    # Format history for prompt
    formatted_history = ""
    for turn in history:
        role = "Student" if turn.get("role") == "user" else "Assistant"
        formatted_history += f"{role}: {turn.get('text', '')}\n"
    
    prompt = f"""
    You are a helpful teaching assistant for this video course. 
    Answer the student's question based strictly on the provided transcript below.
    If the answer is not in the transcript, say "I don't see that covered in the video, but generally..." and give a brief general answer if you know it, but be clear it's not in the video.
    Keep answers concise (2-3 sentences max usually) and conversational.
    
    Transcript:
    {transcript_text}
    
    Chat History:
    {formatted_history}
    
    Student Question: {question}
    """
    
    response = model.generate_content(prompt)
    return response.text
