import os
from dotenv import load_dotenv
from pydantic import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    RAILWAY_API_KEY: str = os.getenv("RAILWAY_API_KEY", "")
    RAILWAY_API_BASE_URL: str = os.getenv("RAILWAY_API_BASE_URL", "https://api.railwayapi.com/v2")
    DEFAULT_QUOTA: str = os.getenv("DEFAULT_QUOTA", "GN")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()