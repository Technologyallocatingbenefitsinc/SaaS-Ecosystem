import google.generativeai as genai
import markdown
from app.config import settings
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

genai.configure(api_key=settings.GEMINI_API_KEY)

def extract_video_id(video_url: str) -> str:
    import re
    patterns = [
        r'(?:v=|/v/|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, video_url)
        if match:
             return match.group(1)
    raise ValueError(f"Invalid YouTube URL: {video_url}")

import httpx
import re
import subprocess
import json
import os

def get_video_metadata(video_url: str):
    """Uses yt-dlp to fetch video metadata as a fallback for transcripts"""
    try:
        # Use python -m yt_dlp to ensure it's found in the current environment
        cmd = [
            "python3", "-m", "yt_dlp", 
            "-j", 
            "--skip-download", 
            "--no-check-certificates",
            "--no-warnings",
            "--geo-bypass",
            "--flat-playlist",
            video_url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            title = data.get("title", "")
            description = data.get("description", "")
            channel = data.get("uploader", "Unknown Channel")
            tags = ", ".join(data.get("tags", [])) if data.get("tags") else "None"
            
            combined_text = f"TITLE: {title}\nCHANNEL: {channel}\nTAGS: {tags}\n\nDESCRIPTION:\n{description}"
            return combined_text
        else:
            print(f"yt-dlp failed (trying scrape fallback): {result.stderr}")
            # FALLBACK: Basic HTML Scrape if yt-dlp is blocked
            try:
                # Synchronous request for metadata
                with httpx.Client(follow_redirects=True, timeout=10) as client:
                    resp = client.get(video_url)
                    if resp.status_code == 200:
                        html = resp.text
                        t_match = re.search(r'<title>(.*?)</title>', html)
                        title_text = t_match.group(1).replace(" - YouTube", "") if t_match else "Unknown Video"
                        
                        d_match = re.search(r'"shortDescription":"(.*?)"', html)
                        desc_text = d_match.group(1).encode().decode('unicode_escape') if d_match else "Description unavailable."
                        
                        return f"TITLE: {title_text}\n\nDESCRIPTION:\n{desc_text}\n\n[Note: Limited data available for this video]"
            except Exception as e:
                print(f"Scrape fallback failed: {e}")
            return None
    except Exception as e:
        print(f"Metadata Fallback Error: {e}")
        return None

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
                print(f"List Transcripts failed for {video_id}: {e}")
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
                        transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                    except:
                        # Just grab the first one we can find?
                        for t in transcript_list:
                            transcript = t
                            break
            
            if not transcript:
                 raise NoTranscriptFound(video_id)

            transcript_data = transcript.fetch()
        
        except (TranscriptsDisabled, NoTranscriptFound) as trans_err:
            print(f"Transcripts unavailable for {video_id}: {trans_err}. Trying metadata fallback...")
            metadata_text = get_video_metadata(video_url)
            if metadata_text:
                return f"[FALLBACK MESSAGE: Transcripts were disabled for this video. Summary is based on video metadata/description.]\n\n{metadata_text}"
            
            # If metadata also fails, raise the original error
            if isinstance(trans_err, TranscriptsDisabled):
                raise ValueError("Subtitles are disabled for this video, and no metadata could be fetched. Cannot generate summary.")
            else:
                raise ValueError("No suitable subtitles found, and no metadata could be fetched. Cannot generate summary.")
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

async def process_video_content(video_url: str, user_tier: str, user_id: int, slide_count: str = "6-10", language: str = "English"):
    transcript = get_transcript(video_url)
    
    if user_tier == "student":
        model_name = "gemini-2.5-flash"
        prompt = f"Summarize the following video transcript into concise bullet points suitable for study notes. Target length: {slide_count} slides/sections. OUTPUT LANGUAGE: {language}.\\n\\n{transcript}"
    elif user_tier == "professor":
        model_name = "gemini-2.5-flash" 
        prompt = f"Create a detailed academic study guide with citations based on the following transcript. Structure the guide into {slide_count} distinct chapters or modules. OUTPUT LANGUAGE: {language}.\\n\\n{transcript}"
    elif user_tier == "podcaster":
        model_name = "gemini-2.5-flash"
        prompt = f"Generate slide descriptions and visual imagery ideas for a presentation based on this transcript. PRODUCE EXACTLY {slide_count} SLIDES. For each slide, provide the text content and a prompt for an image generator. OUTPUT LANGUAGE: {language}.\\n\\n{transcript}"
    else:
        model_name = "gemini-2.5-flash"
        prompt = f"Summarize this. OUTPUT LANGUAGE: {language}.\\n\\n{transcript}"

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

async def convert_text_to_slides_json(text: str, count: int = 10, tone: str = "neutral", html_content: str = None, language: str = "English"):
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    # Use HTML content if valid, otherwise fallback to text
    content_to_process = html_content if html_content and len(html_content) > 50 else text

    style_instructions = {
        "professional": "Use formal, corporate language. Focus on actionable insights, ROI, and strategic value. Avoid slang. Use strong verbs.",
        "fun": "Use a casual, high-energy tone. Include emojis in titles. Use metaphors, humor, and punchy, short sentences. Make it feel like a viral social media post.",
        "academic": "Use scholarly, precise language. Focus on definitions, theoretical frameworks, and evidence. Ensure deep accuracy.",
        "neutral": "Use clear, balanced, and direct language. Avoid emotional coloring or excessive jargon."
    }
    
    specific_instruction = style_instructions.get(tone.lower(), style_instructions["neutral"])

    prompt = f"""
    Convert the following content into a JSON structure for a PowerPoint presentation.
    Create exactly {count} slides.
    
    STYLE INSTRUCTION: {specific_instruction}
    Tone: {tone}
    OUTPUT LANGUAGE: {language}
    
    IMPORTANT: The content may contain HTML <img> tags. If you find an image that is relevant to a specific slide's topic, extract its 'src' attribute and include it in the "image_url" field for that slide.
    
    Output must be a plain JSON list of objects. Each object must have:
    - "title": string (translated to {language})
    - "points": list of strings (translated to {language})
    - "notes": string (translated to {language})
    - "image_url": string (optional, the src URL of the image if one belongs on this slide)
    
    Ensure the JSON is valid and properly formatted. Do not include markdown code blocks.
    
    Content:
    {content_to_process}
    """
    response = model.generate_content(prompt)
    
    # Clean markdown if present
    cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
    return cleaned_text

async def generate_quiz_from_text(text: str, language: str = "English"):
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Create a multiple-choice quiz based on the following text.
    Generate 5 to 10 questions.
    OUTPUT LANGUAGE: {language}
    
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

async def generate_flashcards_from_text(text: str, language: str = "English"):
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    Create a set of flashcards based on the key concepts in the following text.
    Generate 5 to 15 cards.
    OUTPUT LANGUAGE: {language}
    
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
    # Remove accidental double cleaning
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

async def generate_audio_script(transcript_text: str, language: str = "English"):
    model = genai.GenerativeModel("gemini-2.0-flash-thinking-exp-01-21")
    prompt = f"""
    Convert the following transcript into a natural, engaging podcast dialogue between two hosts:
    
    1. **Alex (The Host)**: Curious, enthusiastic, asks clarifying questions, uses analogies.
    2. **Sam (The Expert)**: Knowledgeable, calm, explains concepts clearly but not dryly.
    
    The dialogue should be about 3-5 minutes of reading time (approx 600-800 words).
    Focus on the core insights. Use "Um", "Exactly", "Right?" to make it sound natural.
    OUTPUT LANGUAGE: {language}
    
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
