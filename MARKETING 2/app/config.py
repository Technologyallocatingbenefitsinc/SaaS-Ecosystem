from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    DATABASE_URL: str
    AUTH_SECRET_TOKEN: str
    
    class Config:
        env_file = ".env"

settings = Settings()
