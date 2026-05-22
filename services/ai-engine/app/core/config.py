from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os

class Settings(BaseSettings):
    NODE_ID: str = "node_001"
    MAX_CAMERAS: int = 4
    SAMPLING_FPS: int = 15
    ARTIFACTS_DIR: str = "d:/Projects/vision ai/storage/models"
    API_KEY: str = ""  # Empty string means disabled/dev mode

    # Database
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "admin123"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "ai_surveillance"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # AI Config
    DETECTION_THRESHOLD: float = 0.45
    RECOGNITION_THRESHOLD: float = 0.50
    TRACK_BUFFER: int = 45

    model_config = SettingsConfigDict(
        env_file=os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../config/ai-engine.env")), 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
