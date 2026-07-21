"""Chase export parsing — both export variants, no database involved."""

from datetime import date
from decimal import Decimal

import pytest

from app.errors import ApiError
from app.services.chase_parser import (
    CHECKING,
    CREDIT_CARD,
    detect_variant,
    dominant_month,
    parse_chase_file,
)


def test_detects_credit_card_variant() -> None:
    columns = ["transaction date", "post date", "description", "category", "type", "amount", "memo"]
    assert detect_variant(columns) == CREDIT_CARD


def test_detects_checking_variant() -> None:
    columns = ["details", "posting date", "description", "amount", "type", "balance"]
    assert detect_variant(columns) == CHECKING


def test_rejects_unrecognised_headers() -> None:
    with pytest.raises(ApiError) as excinfo:
        detect_variant(["foo", "bar"])
    assert excinfo.value.status == 422


def test_parses_credit_card_export(credit_card_csv: bytes) -> None:
    rows = parse_chase_file(credit_card_csv, "chase_credit_2026-08.csv")
    assert len(rows) == 13

    groceries = rows[0]
    assert groceries.date == date(2026, 8, 2)
    assert groceries.description == "WHOLEFDS MKT #10259"
    assert groceries.chase_category == "Groceries"
    # Amounts are stored positive; the sign in the file only sets direction.
    assert groceries.amount == Decimal("86.42")
    assert groceries.kind == "expense"


def test_credit_card_positive_amounts_are_income(credit_card_csv: bytes) -> None:
    rows = parse_chase_file(credit_card_csv, "chase_credit_2026-08.csv")
    income = [r for r in rows if r.kind == "income"]
    assert {r.description for r in income} == {
        "PAYROLL DIRECT DEP - ACME CORP",
        "RETURN - AMAZON",
    }


def test_parses_checking_export(checking_csv: bytes) -> None:
    rows = parse_chase_file(checking_csv, "chase_checking_2026-09.csv")
    assert len(rows) == 7

    # Direction comes from the Details column, not the amount's sign alone.
    rent = rows[0]
    assert rent.kind == "expense"
    assert rent.amount == Decimal("1850.00")
    assert rent.date == date(2026, 9, 1)

    payroll = rows[1]
    assert payroll.kind == "income"
    # Checking exports carry no category, so the transaction type stands in.
    assert payroll.chase_category == "ACH_CREDIT"


def test_parses_excel_export(credit_card_xlsx: bytes) -> None:
    rows = parse_chase_file(credit_card_xlsx, "chase_credit_2026-08.xlsx")
    assert len(rows) == 13
    assert rows[0].amount == Decimal("86.42")


def test_empty_file_is_rejected() -> None:
    with pytest.raises(ApiError) as excinfo:
        parse_chase_file(b"", "empty.csv")
    assert excinfo.value.status == 422


def test_file_with_only_headers_is_rejected() -> None:
    with pytest.raises(ApiError) as excinfo:
        parse_chase_file(b"Transaction Date,Description,Amount\n", "headers.csv")
    assert excinfo.value.status == 422


def test_zero_and_unparseable_rows_are_skipped() -> None:
    content = (
        b"Transaction Date,Post Date,Description,Category,Type,Amount\n"
        b"08/02/2026,08/03/2026,REAL,Groceries,Sale,-10.00\n"
        b"not-a-date,08/03/2026,BAD DATE,Groceries,Sale,-5.00\n"
        b"08/04/2026,08/05/2026,ZERO,Groceries,Sale,0.00\n"
    )
    rows = parse_chase_file(content, "mixed.csv")
    assert [r.description for r in rows] == ["REAL"]


def test_amount_formats_are_tolerated() -> None:
    content = (
        b"Transaction Date,Post Date,Description,Category,Type,Amount\n"
        b'08/02/2026,08/03/2026,COMMAS,Groceries,Sale,"-1,234.56"\n'
        b"08/03/2026,08/04/2026,PARENS,Groceries,Sale,(78.90)\n"
        b"08/04/2026,08/05/2026,DOLLAR,Groceries,Sale,-$12.00\n"
    )
    rows = parse_chase_file(content, "amounts.csv")
    assert [r.amount for r in rows] == [
        Decimal("1234.56"),
        Decimal("78.90"),
        Decimal("12.00"),
    ]
    assert all(r.kind == "expense" for r in rows)


def test_dominant_month_picks_the_statement_month(checking_csv: bytes) -> None:
    rows = parse_chase_file(checking_csv, "chase_checking_2026-09.csv")
    assert dominant_month(rows) == "2026-09"
