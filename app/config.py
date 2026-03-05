from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import List
import secrets


class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────────
    APP_NAME: str = "VerifAI"
    ENVIRONMENT: str = "development"

    @property
    def DEBUG(self) -> bool:
        """Debug is only enabled in development. Never trust a raw DEBUG env var in prod."""
        return self.ENVIRONMENT == "development"

    # ─── Database ─────────────────────────────────────────────────
    DATABASE_URL: str  # Required — no default. Must be in .env

    # ─── Redis ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ─── JWT / Security ───────────────────────────────────────────
    # Required — no default. Prevents accidental use of a weak fallback key.
    SECRET_KEY: str

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if v in ("default_secret_key", "REPLACE_WITH_A_STRONG_RANDOM_SECRET"):
            raise ValueError(
                "SECRET_KEY is still set to a placeholder. Set a real secret in your .env file."
            )
        return v

    # ─── CORS ─────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:5173"

    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        """Returns safe CORS origins. Wildcard is NEVER used with credentials."""
        if self.ENVIRONMENT == "production":
            # In production, only allow the known frontend origin
            return [self.FRONTEND_URL]
        # Development: allow localhost variants
        return [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:3000",
            self.FRONTEND_URL,
        ]

    # ─── Email ────────────────────────────────────────────────────
    EMAIL_SENDER: str  # Required
    EMAIL_PASSWORD: str  # Required — Gmail App Password
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 465

    # ─── Support ──────────────────────────────────────────────────
    SUPPORT_PHONE: str = "+91-1800-XXXXXXXX"
    SUPPORT_EMAIL: str = "support@verifai.app"

    # ─── Branding ─────────────────────────────────────────────────
    LOGO_URL: str = "https://raw.githubusercontent.com/ethancodes-6969/VerifAI-AgenticAI/main/assets/verifai-logo.png"

    # ─── App URLs ─────────────────────────────────────────────────
    APP_URL: str = "http://localhost:8000"

    # ─── Fraud Detection Thresholds ───────────────────────────────
    FRAUD_HIGH_RISK_THRESHOLD: float = 0.80
    FRAUD_MEDIUM_RISK_THRESHOLD: float = 0.50

    # ─── ML Model Paths ───────────────────────────────────────────
    ML_MODEL_PATH: str = "app/ml/models/xgboost_fraud_model.pkl"
    SCALER_PATH: str = "app/ml/models/scaler.pkl"

    # ─── Google OAuth ─────────────────────────────────────────────
    # Optional — leave empty to disable Google login.
    # Get credentials at: https://console.cloud.google.com/apis/credentials
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    @property
    def GOOGLE_OAUTH_ENABLED(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    # ─── WhatsApp Business API (optional, not yet implemented) ────
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
