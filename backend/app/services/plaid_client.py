"""Thin factory around the Plaid SDK client.

Kept as one function so tests can monkeypatch just this seam with a fake
exposing the handful of calls `services/plaid_sync.py` and
`routers/plaid.py` actually use — `.transactions_sync()`,
`.item_public_token_exchange()`, `.link_token_create()`, `.item_remove()` —
without mocking the whole SDK.
"""

from functools import lru_cache

import plaid
from plaid.api import plaid_api

from app.config import settings

_ENV_HOSTS = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}


@lru_cache
def get_plaid_client() -> plaid_api.PlaidApi:
    configuration = plaid.Configuration(
        host=_ENV_HOSTS.get(settings.plaid_env, plaid.Environment.Sandbox),
        api_key={"clientId": settings.plaid_client_id, "secret": settings.plaid_secret},
    )
    return plaid_api.PlaidApi(plaid.ApiClient(configuration))
