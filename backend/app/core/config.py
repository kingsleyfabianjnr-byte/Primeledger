from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "PrimeLedger"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./primeledger.db"

    # Auth
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_supersecretkey_primeledger_2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # watsonx
    WATSONX_API_KEY: str = ""
    WATSONX_PROJECT_ID: str = ""
    WATSONX_URL: str = "https://us-south.ml.cloud.ibm.com"

    # Frontend URL (set to Vercel URL in Railway env vars)
    FRONTEND_URL: str = "http://localhost:5173"

    # Email (SendGrid)
    SENDGRID_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@primeledger.ai"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
