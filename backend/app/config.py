from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file before settings are initialized
load_dotenv()


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+psycopg://syncboard:syncboard_dev@localhost:5432/syncboard"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60 * 24  # 24 hours

    # CORS — allowed frontend origins
    cors_origins: list[str] = ["http://localhost:5173"]


# Single instance imported throughout the app
settings = Settings()