from gtts import gTTS
import os
import uuid

def synthesize_podcast_audio(script_json: list, output_filename: str = "podcast.mp3") -> str:
    """
    Converts a dialogue script into a single audio file using gTTS.
    Uses unique temp files to prevent clashes during concurrent requests.
    """
    temp_files = []
    
    try:
        for i, line in enumerate(script_json):
            speaker = line.get("speaker", "Unknown")
            text = line.get("text", "")
            
            if not text: continue
            
            # Choose accent/TLD
            tld = 'com'
            if speaker == "Sam" or "Expert" in speaker:
                tld = 'co.uk'
            
            # Generate unique clip
            temp_name = f"temp_{uuid.uuid4().hex}.mp3"
            tts = gTTS(text, lang='en', tld=tld)
            tts.save(temp_name)
            temp_files.append(temp_name)
            
        # Combine MP3s
        with open(output_filename, 'wb') as outfile:
            for fname in temp_files:
                if os.path.exists(fname):
                    with open(fname, 'rb') as infile:
                        outfile.write(infile.read())
                    os.remove(fname)
                    
    except Exception as e:
        print(f"Audio Synthesis Error: {e}")
        # Cleanup any remaining temps
        for fname in temp_files:
            if os.path.exists(fname):
                try: os.remove(fname)
                except: pass
        raise e
            
    return output_filename
