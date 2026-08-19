import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    RAILWAY_API_KEY: str = os.getenv("RAILWAY_API_KEY", "")
    # Base URL for railkit API (include /api)
    RAILWAY_API_BASE_URL: str = os.getenv("RAILWAY_API_BASE_URL", "https://railkit-api.rajivdubey.dev/api")
    DEFAULT_QUOTA: str = os.getenv("DEFAULT_QUOTA", "GN")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow",
    }

settings = Settings()