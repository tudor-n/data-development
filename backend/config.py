from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    cors_origins: List[str]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

settings = Settings()