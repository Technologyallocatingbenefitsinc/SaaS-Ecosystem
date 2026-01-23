import asyncio
import os
import sys

# Mock settings
os.environ["GEMINI_API_KEY"] = "mock"

# Force current dir in path
sys.path.append(os.getcwd())

from app.services.gemini_engine import get_transcript, extract_video_id

def test_extract_shorts():
    urls = [
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ?feature=share",
        "http://www.youtube.com/shorts/dQw4w9WgXcQ"
    ]
    for url in urls:
        vid = extract_video_id(url)
        print(f"URL: {url} -> ID: {vid}")
        assert vid == "dQw4w9WgXcQ"

async def test_fallback_logic():
    # This might fail on transcripts but hopefully metadata works or scrape works
    # Using a video that is likely public
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"\nTesting {test_url}...")
    try:
        content = get_transcript(test_url)
        print("Content fetched successfully (Length: {})".format(len(content)))
        print(content[:200] + "...")
    except Exception as e:
        print(f"Error as expected: {e}")

if __name__ == "__main__":
    test_extract_shorts()
    asyncio.run(test_fallback_logic())
