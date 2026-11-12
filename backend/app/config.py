from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    security_mode: str = "vulnerable"
    training_ack: bool = True
    vuln_disable: str = ""

    database_url: str = "sqlite:///./vulncrm.db"
    redis_url: str = ""
    keys_dir: str = "./keys"
    upload_dir: str = "./uploads"
    static_dir: str = "./static"
    public_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173"

    jwt_issuer: str = "https://vulncrm.local"
    access_ttl_seconds: int = 3600
    partial_ttl_seconds: int = 300
    otp_ttl_seconds: int = 300
    session_ttl_hours: int = 12
    oauth_code_ttl: int = 120
    oauth_access_ttl: int = 3600
    oauth_refresh_ttl: int = 86400 * 30
    bcrypt_rounds: int = 10

    idp_base_url: str = "http://localhost:9000"
    node_service_url: str = "http://localhost:3100"
    seed_on_start: bool = True
    seed_password: str = "Crm#Pass2026"
    rate_limit_multiplier: int = 1

    @property
    def sqlalchemy_url(self) -> str:
        u = self.database_url
        if u.startswith("postgres://"):
            u = "postgresql://" + u[len("postgres://"):]
        if u.startswith("postgresql://"):
            u = "postgresql+psycopg://" + u[len("postgresql://"):]
        return u

    @property
    def training_allowed(self) -> bool:
        return self.environment in ("local", "training", "development", "test") and self.training_ack


@lru_cache
def get_settings() -> Settings:
    return Settings()
