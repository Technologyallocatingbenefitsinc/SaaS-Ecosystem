
from youtube_transcript_api import YouTubeTranscriptApi
import sys

print("Testing instantiation and list...")
try:
    yt = YouTubeTranscriptApi()
    print("Instance created.")
    try:
        # Just check if 'list' interacts like a function
        print("yt.list exists:", hasattr(yt, 'list'))
        # We can't actually call it without a real video ID that works and network, 
        # but we can see if it IS a method.
        print("yt.list is callable:", callable(yt.list))
    except Exception as e:
        print("Error checking list:", e)
except Exception as e:
    print("Error instantiating:", e)
    # Check if they are static
    print("Checking static list:")
    try:
        print("YouTubeTranscriptApi.list is callable:", callable(YouTubeTranscriptApi.list))
    except:
        pass
