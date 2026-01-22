import requests
import os

# Create a dummy image
with open("test image.png", "wb") as f:
    f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

url = "http://localhost:8000/upload/upload-content"
files = {'file': open('test image.png', 'rb')}

# Need to authenticate or mock user. The endpoint depends on auth.get_replit_user.
# If running with AUTH_SECRET_TOKEN=test, we might need to bypass or mock the headers.
# But get_replit_user reads headers like X-Replit-User-Id.
# We'll assume the mock server is running or we need to start it with loose auth.

headers = {
    "X-Replit-User-Id": "1",
    "X-Replit-User-Name": "testuser",
    "X-Replit-User-Roles": "student"
}

try:
    print("Uploading...")
    response = requests.post(url, files=files, headers=headers)
    print(f"Upload Status: {response.status_code}")
    print(f"Upload Response: {response.text}")

    if response.status_code == 200:
        data = response.json()
        raw_path = data['path']
        print(f"Raw Path: {raw_path}")
        
        # Simulate frontend logic
        web_path = raw_path.replace('user_uploads', '/uploads')
        print(f"Web Path: {web_path}")
        
        # Verify access (request library encodes spaces automatically usually, or we format it)
        # requests.get handles encoding if passing params, but for raw URL string we expect it to work or we encode it
        img_response = requests.get(f"http://localhost:8000{web_path}") # requests should encode current path or handle it
        print(f"Image Access Status: {img_response.status_code}")
        
except Exception as e:
    print(f"Error: {e}")
finally:
    if os.path.exists("test image.png"):
        os.remove("test image.png")
