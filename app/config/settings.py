"""Application configuration settings."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    APP_NAME: str = "Pend Claim Analysis"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    LOGS_DIR: Path = BASE_DIR / "logs"
    DATA_DIR: Path = BASE_DIR / "data"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{DATA_DIR}/claims.db"

    # Gemini
    GEMINI_API_KEY: str
    
    # Logging
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra='ignore')


# Create instance of settings
settings = Settings()

# Create necessary directories
settings.LOGS_DIR.mkdir(exist_ok=True)
settings.DATA_DIR.mkdir(exist_ok=True)
