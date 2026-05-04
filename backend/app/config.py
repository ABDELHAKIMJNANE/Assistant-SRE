"""Configuration centralisée — lecture des variables d'environnement."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Toutes les variables d'environnement du backend.
    En local : lues depuis le fichier .env
    En AKS   : injectées par K8s Secrets (CSI Driver → Key Vault)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──
    app_version: str = "1.0.0"
    environment: str = "development"

    # ── MongoDB / Cosmos DB ──
    mongodb_url: str = "mongodb://mongodb:27017"
    mongodb_db_name: str = "aiops_db"

    # ── Azure OpenAI ──
    openai_endpoint: str = ""
    openai_api_key: str = ""
    openai_deployment: str = "gpt-35-turbo"
    openai_api_version: str = "2024-02-01"

    # ── Observabilité ──
    loki_url: str = "http://loki:3100"
    prometheus_url: str = "http://prometheus:9090"

    # ── Email Outlook ──
    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    sre_email: str = ""

    # ── Logging ──
    log_level: str = "INFO"

    # ── Rate Limiting ──
    rate_limit_requests: int = 100
    rate_limit_period: int = 60  # seconds


settings = Settings()
