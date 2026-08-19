import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    RAILWAY_API_KEY: str = os.getenv("RAILWAY_API_KEY", "")
    RAILWAY_API_BASE_URL: str = os.getenv("RAILWAY_API_BASE_URL", "https://api.railwayapi.com/v2")
    # Optional explicit endpoints (override default /v2/...)
    TRAIN_ENDPOINT: str = os.getenv("TRAIN_ENDPOINT", "/v2/train")
    STATION_ENDPOINT: str = os.getenv("STATION_ENDPOINT", "/v2/station")
    AVAILABILITY_ENDPOINT: str = os.getenv("AVAILABILITY_ENDPOINT", "/v2/availability")
    DEFAULT_QUOTA: str = os.getenv("DEFAULT_QUOTA", "GN")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()