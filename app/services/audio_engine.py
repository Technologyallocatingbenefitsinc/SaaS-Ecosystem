from gTTS import gTTS
import os
from pathlib import Path

def synthesize_podcast_audio(script_json: list, output_filename: str = "podcast.mp3") -> str:
    """
    Converts a dialogue script into a single audio file.
    Since gTTS only has one voice, we currently valid just read it.
    Future improvement: Pitch shifting or different regional accents (e.g. 'co.uk' vs 'com') 
    to simulate two speakers.
    """
    combined_text = ""
    
    # Simple strategy: Alternating accents?
    # Alex (Host) = 'us' (Americans)
    # Sam (Expert) = 'co.uk' (British)
    
    temp_files = []
    
    for i, line in enumerate(script_json):
        speaker = line.get("speaker", "Unknown")
        text = line.get("text", "")
        
        # skip empty
        if not text: continue
        
        # Choose accent
        tld = 'com'
        if speaker == "Sam" or "Expert" in speaker:
            tld = 'co.uk'
        
        # Generate clip
        tts = gTTS(text, lang='en', tld=tld)
        filename = f"temp_{i}.mp3"
        tts.save(filename)
        temp_files.append(filename)
        
    # Combine (Concatenate MP3s purely by bytes - works for simple MP3 streams usually)
    with open(output_filename, 'wb') as outfile:
        for fname in temp_files:
            with open(fname, 'rb') as infile:
                outfile.write(infile.read())
            # Cleanup temp
            os.remove(fname)
            
    return output_filename
