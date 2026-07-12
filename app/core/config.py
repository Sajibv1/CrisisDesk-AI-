from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Citizen Report Triage API"
    environment: str = "development"
    database_url: str = Field(default="postgresql+psycopg://citizen_reports:citizen_reports@localhost:5432/citizen_reports", alias="DATABASE_URL")
    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="admin123", alias="ADMIN_PASSWORD")
    jwt_secret_key: str = Field(default="change-me-in-production", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    rate_limit_per_minute: int = 60
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = "gemini-1.5-flash"
    libretranslate_url: str = "https://libretranslate.de/translate"
    nominatim_url: str = "https://nominatim.openstreetmap.org/search"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
