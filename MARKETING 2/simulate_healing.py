import asyncio
import httpx
from app.config import settings

# Mock configuration for the test
settings.AUTH_SECRET_TOKEN = "test_token"

async def test_self_healing():
    print("--- Simulating n8n Error Trigger ---")
    
    # 1. The Crash (Simulated Payload from n8n)
    n8n_error_payload = {
        "node": "YouTube Search",
        "message": "404 Not Found: Transcript is empty"
    }
    
    # 2. The Signal (n8n POSTs to Replit)
    # We use app directly to avoid needing a running server for this quick test, 
    # but normally this hits https://your-app.com/debug-fix
    from app.main import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    
    print(f"Sending Error Signal: {n8n_error_payload}")
    
    response = client.post(
        "/debug-fix",
        json=n8n_error_payload,
        headers={"x-n8n-auth": "test_token"}
    )
    
    print(f"Response Status: {response.status_code}")
    print(f"Response Body: {response.json()}")
    print("--------------------------------------")
    print("✅ Check your terminal output above for the 'CRITICAL_ERROR_LOG' message.")
    print("   That message is what wakes up Antigravity to fix the code.")

if __name__ == "__main__":
    asyncio.run(test_self_healing())
