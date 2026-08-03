"""Encryption for stored Plaid access tokens.

The rest of the app's config lives in `.env` in plaintext (same trust model as
the Pi's disk), but a Plaid access token is a live bank credential rather than
local config, so it's kept encrypted at rest with a key that isn't the
database itself. Losing `PLAID_TOKEN_ENCRYPTION_KEY` means re-linking, not
decrypting old data — acceptable for a single-user app with no rotation
tooling.
"""

from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import settings
from app.errors import ApiError


@lru_cache
def _fernet() -> Fernet:
    if not settings.plaid_token_encryption_key:
        raise ApiError("PLAID_TOKEN_ENCRYPTION_KEY is not configured.", 500)
    return Fernet(settings.plaid_token_encryption_key.encode())


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
