"""Test fixtures.

Tests run against a real PostgreSQL database (`custodian_test`) rather than
SQLite: the app leans on `Numeric` arithmetic, `to_char` date formatting and
JSONB, none of which SQLite reproduces faithfully. Each test starts from a
truncated database with only the base seed loaded.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  -- registers tables on Base.metadata
from app.config import settings
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.seed import seed_base

FIXTURES = Path(__file__).parent / "fixtures"

engine = create_engine(settings.test_database_url, future=True)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

TABLES = (
    "transactions",
    "import_batches",
    "holdings",
    "price_quotes",
    "net_worth_snapshots",
    "chase_category_map",
    "accounts",
    "categories",
)


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    with TestingSession() as session:
        seed_base(session)
    yield


@pytest.fixture
def db() -> Iterator[Session]:
    with TestingSession() as session:
        yield session


@pytest.fixture
def client() -> Iterator[TestClient]:
    def override() -> Iterator[Session]:
        with TestingSession() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def credit_card_csv() -> bytes:
    return (FIXTURES / "chase_credit_2026-08.csv").read_bytes()


@pytest.fixture
def checking_csv() -> bytes:
    return (FIXTURES / "chase_checking_2026-09.csv").read_bytes()


@pytest.fixture
def credit_card_xlsx() -> bytes:
    return (FIXTURES / "chase_credit_2026-08.xlsx").read_bytes()
