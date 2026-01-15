from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    DATABASE_URL: str
    AUTH_SECRET_TOKEN: str
    N8N_WEBHOOK_URL: str = "https://your-n8n-instance.com/webhook/generic"
    N8N_API_KEY: str = "mock_key"
    N8N_UPLOAD_WEBHOOK: str = "https://your-n8n-instance.com/webhook/process-upload"
    N8N_PURGE_WEBHOOK: str = "https://your-n8n-instance.com/webhook/purge-user"
    N8N_TOKEN_LOGGER_URL: str = "https://your-n8n-instance.com/webhook/token-logger"
    STRIPE_SECRET_KEY: str = "mock_key"
    
    model_config = ConfigDict(env_file=".env")

settings = Settings()
