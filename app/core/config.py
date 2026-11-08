from functools import lru_cache
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "dev"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/emailagent"
    api_key: str = "change-me"
    secret_key: str = "change-me-too"
    encryption_key: str
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8080/api/v1/mailboxes/oauth/gmail/callback"
    browser_username: str = Field(default="admin", min_length=1, max_length=100)
    browser_password_hash: str = ""
    frontend_origin: str = "http://localhost:4200"
    session_ttl_seconds: int = Field(default=28800, ge=300, le=86400)
    agent_max_cost_usd: float | None = Field(default=None, gt=0)
    llm_input_usd_per_million: float | None = Field(default=None, ge=0)
    llm_output_usd_per_million: float | None = Field(default=None, ge=0)
    agent_max_output_tokens: int = Field(default=2048, ge=256, le=8192)
    agent_max_steps: int = Field(default=4, ge=1, le=8)
    agent_timeout_seconds: int = Field(default=180, ge=10, le=600)
    agent_max_input_chars: int = Field(default=120000, ge=1000, le=500000)
    llm_model: str = "openai:gpt-4o-mini"
    allow_cloud_processing: bool = False
    redact_pii: bool = True
    review_confidence_threshold: float = Field(default=0.7, ge=0, le=1)
    sync_initial_days: int = Field(default=7, ge=1, le=365)
    poll_interval_seconds: int = Field(default=60, ge=1)
    max_body_chars: int = Field(default=6000, ge=100, le=50000)
    max_processing_attempts: int = Field(default=5, ge=1, le=20)
    retry_base_seconds: int = Field(default=30, ge=1, le=3600)
    api_requests_per_minute: int = Field(default=120, ge=1)
    retention_days: int = Field(default=30, ge=1)
    draft_template: str = Field(default="Be helpful and concise. Ask for missing details. Do not invent commitments.", max_length=4000)

    @model_validator(mode="after")
    def validate_security(self):
        Fernet(self.encryption_key.encode())
        prices = (self.llm_input_usd_per_million, self.llm_output_usd_per_million)
        if (prices[0] is None) != (prices[1] is None):
            raise ValueError("Configure both input and output model prices")
        if self.agent_max_cost_usd is not None and prices[0] is None:
            raise ValueError("An agent cost budget requires configured model prices")
        if not self.api_key or not self.secret_key:
            raise ValueError("API_KEY and SECRET_KEY must not be empty")
        if self.app_env not in {"dev", "test"}:
            if len(self.api_key) < 32 or len(self.secret_key) < 32:
                raise ValueError("Production API_KEY and SECRET_KEY must each be at least 32 characters")
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Production requires Postgres")
            if self.browser_password_hash and not self.frontend_origin.startswith("https://"):
                raise ValueError("Production browser origin must use HTTPS")
            if not self.google_redirect_uri.startswith("https://"):
                raise ValueError("Production OAuth redirect must use HTTPS")
        return self

    @property
    def psycopg_conninfo(self):
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")

@lru_cache
def get_settings():
    return Settings()
