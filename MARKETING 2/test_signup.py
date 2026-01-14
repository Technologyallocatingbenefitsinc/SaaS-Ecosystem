import requests
import os

# 1. Load your Secrets from Replit Environment
# For local testing, you can set these manually or export them in your shell
N8N_WEBHOOK_URL = os.environ.get('N8N_WEBHOOK_URL', 'https://your-n8n-instance.com/webhook/signup')
AUTH_TOKEN = os.environ.get('AUTH_SECRET_TOKEN', 'test_token')

# 2. Mock Data for a "Student" Signup
test_user = {
    "email": "test-student@university.edu",
    "plan": "Student",
    "price": 9.99,
    "university": "State College",
    "event_type": "new_signup"
}

# 3. Secure Headers
headers = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    # If using the 'Header Auth' method in n8n, it might strip 'Bearer', 
    # so we can also send it as a custom header if needed, but standard is Authorization.
}

def trigger_test():
    print(f"🚀 Sending test signup to n8n at {N8N_WEBHOOK_URL}...")
    try:
        response = requests.post(N8N_WEBHOOK_URL, json=test_user, headers=headers)
        
        if response.status_code == 200:
            print("✅ SUCCESS: n8n received the data!")
            print(f"Response: {response.text}")
        else:
            print(f"❌ FAILED: Received {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ FAILED: Could not connect to n8n. Error: {e}")

if __name__ == "__main__":
    if N8N_WEBHOOK_URL == 'https://your-n8n-instance.com/webhook/signup':
        print("⚠️  WARNING: You haven't set N8N_WEBHOOK_URL yet.")
        print("   Please export it or set it in the script before running.")
    trigger_test()
