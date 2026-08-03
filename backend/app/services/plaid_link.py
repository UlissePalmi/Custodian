"""Plaid Link lifecycle: creating a link token, exchanging it for an Item,
listing connections, and unlinking.

Kept separate from `services/plaid_sync.py`, which only ever runs against
already-linked `PlaidItem` rows.
"""

from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import ApiError
from app.models import PlaidItem
from app.services.crypto import decrypt_token, encrypt_token
from app.services.plaid_client import get_plaid_client
from app.services.plaid_sync import sync_item


def create_link_token(db: Session) -> str:
    client = get_plaid_client()
    kwargs = dict(
        user=LinkTokenCreateRequestUser(client_user_id="custodian-single-user"),
        client_name="Custodian",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )
    # Omitted rather than passed as None: the SDK's request model rejects a
    # None value outright, it must not be present at all when unconfigured.
    if settings.plaid_redirect_uri:
        kwargs["redirect_uri"] = settings.plaid_redirect_uri
    response = client.link_token_create(LinkTokenCreateRequest(**kwargs))
    return response.link_token


def exchange_public_token(db: Session, public_token: str, institution_name: str | None) -> PlaidItem:
    """Exchanges Link's public token for a persisted access token, then runs
    the item's first sync so the connection shows data immediately."""
    client = get_plaid_client()
    response = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=public_token)
    )
    item = PlaidItem(
        item_id=response.item_id,
        access_token_encrypted=encrypt_token(response.access_token),
        institution_name=institution_name or "Connected bank",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    sync_item(db, item)
    db.refresh(item)
    return item


def list_connections(db: Session) -> list[PlaidItem]:
    return list(db.scalars(select(PlaidItem)))


def disconnect_item(db: Session, item_id: str) -> None:
    """Unlinks the item. Past transactions/batches are untouched — reversing a
    specific sync's ledger effect is `DELETE /api/import/batches/{id}`, a
    separate action."""
    item = db.scalar(select(PlaidItem).where(PlaidItem.item_id == item_id))
    if item is None:
        raise ApiError("Plaid connection not found.", 404)

    client = get_plaid_client()
    try:
        client.item_remove(ItemRemoveRequest(access_token=decrypt_token(item.access_token_encrypted)))
    except Exception:
        pass  # Best-effort — the item is unlinked locally regardless.

    db.delete(item)
    db.commit()
