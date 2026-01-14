from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    DATABASE_URL: str
    AUTH_SECRET_TOKEN: str
    N8N_UPLOAD_WEBHOOK: str = "https://your-n8n-instance.com/webhook/process-upload"
    
    class Config:
        env_file = ".env"

settings = Settings()
