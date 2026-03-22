from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://leadflow:leadflow_dev_password@localhost:5432/leadflow"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-secret-key-change-in-production"

    # AI Provider: "kimi" or "anthropic"
    ai_provider: str = "kimi"

    # Kimi 2.5 (Moonshot AI) - OpenAI compatible API
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "kimi-latest"

    # Anthropic Claude (optional fallback)
    anthropic_api_key: str = ""

    # WhatsApp
    whatsapp_business_token: str = ""
    whatsapp_phone_number_id: str = ""

    # Telegram
    telegram_bot_token: str = ""

    # Facebook
    facebook_app_id: str = ""
    facebook_app_secret: str = ""
    facebook_access_token: str = ""

    access_token_expire_minutes: int = 1440  # 24 hours
    algorithm: str = "HS256"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
