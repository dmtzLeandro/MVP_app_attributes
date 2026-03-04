from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = "local"
    APP_URL: str = "http://localhost:8000"

    DB_URL: str

    TN_CLIENT_ID: str
    TN_CLIENT_SECRET: str
    TN_OAUTH_BASE: str = "https://www.tiendanube.com"
    TN_API_BASE: str = "https://api.tiendanube.com/2025-03"

    REDIS_URL: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()