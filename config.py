import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    RAILWAY_API_KEY: str = os.getenv("RAILWAY_API_KEY", "")
    # Base domain only — every RailKit endpoint path already starts with /api/...
    RAILWAY_API_BASE_URL: str = os.getenv("RAILWAY_API_BASE_URL", "https://railkit-api.rajivdubey.dev")
    # RailKit signs every request with HMAC-SHA256 using this secret (in addition to x-api-key).
    # This is the SDK's built-in default secret — override via env only if RailKit ever rotates it.
    RAILWAY_SDK_SIGNING_SECRET: str = os.getenv(
        "RAILWAY_SDK_SIGNING_SECRET",
        "97c56e08b27b161124f88acd4f24d1bd50f48075f11dc23b9ea6c0bc9b2f8794",
    )
    DEFAULT_QUOTA: str = os.getenv("DEFAULT_QUOTA", "GN")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow",
    }

settings = Settings()