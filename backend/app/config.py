from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://custodian:custodian@localhost:5432/custodian"
    test_database_url: str = "postgresql+psycopg://custodian:custodian@localhost:5432/custodian_test"

    quote_ttl_minutes: int = 15

    #: Origins allowed to call the API. Matches the front end's port on any
    #: host, so the LAN address and a Tailscale name both work.
    cors_origin_regex: str = r"http://[^/]+:5173"

    #: Plaid API credentials. Empty by default so the app still boots without
    #: bank sync configured; the Plaid endpoints fail loudly if used unset.
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"
    plaid_redirect_uri: str = ""
    #: Fernet key encrypting stored Plaid access tokens. Generate with:
    #: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    plaid_token_encryption_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
