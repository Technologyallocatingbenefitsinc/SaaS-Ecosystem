from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, base_url="http://localhost")

def test_homepage():
    try:
        response = client.get("/")
        print(f"Status: {response.status_code}")
        if response.status_code >= 500:
            print("ERROR: Server Error on Homepage")
            print(response.text)
        else:
            print("Homepage seems OK or redirected")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_homepage()
