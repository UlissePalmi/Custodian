"""Chase export parsing.

Three export shapes exist:

* credit card CSV/XLSX — Transaction Date, Post Date, Description, Category,
  Type, Amount. Purchases are negative; payments and refunds are positive.
* checking CSV/XLSX — Details, Posting Date, Description, Amount, Type,
  Balance. Direction comes from Details (DEBIT/CREDIT), with the amount's
  sign as a fallback. There is no category column, so rows arrive
  uncategorised and get flagged for review downstream.
* the "Spending Report" PDF — Chase's category-grouped year-to-date summary,
  the only export format Chase actually offers for this. Every row from
  every month in the report is returned; the importer is responsible for
  dropping what's out of range or already in the ledger. See
  `_parse_spending_report_pdf` for its shape and the sign convention, which
  is the *opposite* of the CSV/XLSX credit card export.

This module is deliberately free of database and HTTP concerns: it turns bytes
into rows so it can be tested against fixture files on its own.
"""

import io
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pandas as pd

from app.errors import ApiError

CREDIT_CARD = "credit_card"
CHECKING = "checking"

_DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d/%m/%Y")

_CREDIT_REQUIRED = {"transaction date", "description", "amount"}
_CHECKING_REQUIRED = {"posting date", "description", "amount"}

# Spending Report PDF: a category name is a standalone all-caps/underscore
# line (e.g. "BILLS_AND_UTILITIES"), immediately or eventually followed by a
# "Transaction Date ... Amount" header starting that category's table, which
# runs until a "Total $x" line. A table that continues onto the next page
# repeats the header but not the category name, hence `_pending_category`
# persisting across pages rather than resetting per table.
_CATEGORY_LINE = re.compile(r"^[A-Z][A-Z]*(?:_[A-Z]+)*$")
_DETAIL_HEADER = re.compile(r"^Transaction Date\s+Posted Date\s+Description\s+Amount$")
_TOTAL_LINE = re.compile(r"^Total\s+\$")
_TRANSACTION_LINE = re.compile(
    r"^(?P<tdate>[A-Za-z]{3} \d{2}, \d{4})\s+"
    r"[A-Za-z]{3} \d{2}, \d{4}\s+"  # posted date, unused: transaction date is what months are keyed on
    r"(?P<description>.+?)\s+"
    r"\$(?P<amount>-?[\d,]+\.\d{2})$"
)


@dataclass(frozen=True)
class ParsedRow:
    date: date
    description: str
    chase_category: str
    amount: Decimal  # always positive
    kind: str  # 'income' | 'expense'


def _normalise(header: object) -> str:
    return str(header).strip().lower().replace("﻿", "")


def _read_frame(content: bytes, filename: str) -> pd.DataFrame:
    lower = filename.lower()
    try:
        if lower.endswith((".xls", ".xlsx")):
            frame = pd.read_excel(io.BytesIO(content), dtype=str)
        else:
            frame = pd.read_csv(io.BytesIO(content), dtype=str)
    except Exception as exc:  # noqa: BLE001 - any parse failure is a user-facing 422
        raise ApiError(f"Could not read that file: {exc}", 422) from exc

    frame.columns = [_normalise(c) for c in frame.columns]
    return frame


def detect_variant(columns: list[str]) -> str:
    present = set(columns)
    if "details" in present and _CHECKING_REQUIRED <= present:
        return CHECKING
    if _CREDIT_REQUIRED <= present:
        return CREDIT_CARD
    if _CHECKING_REQUIRED <= present:
        return CHECKING
    raise ApiError(
        "That does not look like a Chase export — expected a credit card or checking activity file.",
        422,
    )


def _parse_date(value: object) -> date | None:
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(text, errors="coerce")
    except Exception:  # noqa: BLE001
        return None
    return None if pd.isna(parsed) else parsed.date()


def _parse_amount(value: object) -> Decimal | None:
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text or text.lower() in {"nan", "none"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    return -amount if negative else amount


def _humanize_category(name: str) -> str:
    """"BILLS_AND_UTILITIES" -> "Bills & Utilities", matching the CSV export's
    category spelling closely enough to hit the existing Chase category map
    for the common cases (Groceries, Personal, Shopping, Travel, ...)."""
    return name.replace("_AND_", " & ").replace("_", " ").title()


def _parse_spending_report_pdf(content: bytes) -> list[ParsedRow]:
    """Chase's "Spending Report" PDF: the only export Chase actually offers.

    It's a year-to-date summary, category by category, each with its own
    "Transaction Date / Posted Date / Description / Amount" table ending in a
    "Total $x" line — not a monthly statement. This always contains every
    month since January, so every row is returned here; it's on the caller
    (`build_preview` in `services/importer.py`) to drop what's out of the
    ledger's range and what's already in the database.

    Sign convention here is the opposite of the CSV credit-card export:
    a positive amount is money spent, negative is a refund/credit.
    """
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:  # noqa: BLE001 - any parse failure is a user-facing 422
        raise ApiError(f"Could not read that file: {exc}", 422) from exc

    rows: list[ParsedRow] = []
    pending_category: str | None = None
    category: str | None = None
    in_table = False

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if _DETAIL_HEADER.match(line):
            category = pending_category
            in_table = category is not None
            continue

        if in_table and _TOTAL_LINE.match(line):
            in_table = False
            continue

        if in_table:
            match = _TRANSACTION_LINE.match(line)
            if match:
                parsed_date = _parse_date(match.group("tdate"))
                amount = _parse_amount(match.group("amount"))
                if parsed_date is None or amount is None or amount == 0:
                    continue
                rows.append(
                    ParsedRow(
                        date=parsed_date,
                        description=match.group("description").strip(),
                        chase_category=_humanize_category(category),
                        amount=abs(amount),
                        # Spending Report convention: positive = spent, negative = refunded.
                        kind="income" if amount < 0 else "expense",
                    )
                )
            continue

        if _CATEGORY_LINE.match(line):
            pending_category = line

    if not rows:
        raise ApiError("No transactions found in that file.", 422)

    return rows


def parse_chase_file(content: bytes, filename: str) -> list[ParsedRow]:
    if not content:
        raise ApiError("That file is empty.", 422)

    if filename.lower().endswith(".pdf"):
        return _parse_spending_report_pdf(content)

    frame = _read_frame(content, filename)
    if frame.empty:
        raise ApiError("That file is empty.", 422)

    variant = detect_variant(list(frame.columns))
    date_column = "transaction date" if variant == CREDIT_CARD else "posting date"
    if date_column not in frame.columns:
        date_column = "post date" if "post date" in frame.columns else date_column

    rows: list[ParsedRow] = []
    for _, raw in frame.iterrows():
        parsed_date = _parse_date(raw.get(date_column))
        amount = _parse_amount(raw.get("amount"))
        if parsed_date is None or amount is None or amount == 0:
            continue

        description = str(raw.get("description") or "").strip() or "(no description)"
        kind = _kind_for(variant, raw, amount)

        if variant == CREDIT_CARD:
            chase_category = str(raw.get("category") or "").strip()
        else:
            # Checking exports have no category; the transaction type is the
            # only hint available, and it rarely maps, so most rows end up
            # flagged for review.
            chase_category = str(raw.get("type") or "").strip()

        rows.append(
            ParsedRow(
                date=parsed_date,
                description=description,
                chase_category=chase_category,
                amount=abs(amount),
                kind=kind,
            )
        )

    if not rows:
        raise ApiError("No transactions found in that file.", 422)
    return rows


def _kind_for(variant: str, raw: pd.Series, amount: Decimal) -> str:
    if variant == CHECKING:
        details = str(raw.get("details") or "").strip().upper()
        if details == "DEBIT":
            return "expense"
        if details == "CREDIT":
            return "income"
    return "expense" if amount < 0 else "income"


def dominant_month(rows: list[ParsedRow]) -> str | None:
    """The month most rows fall in — statements can straddle a boundary."""
    if not rows:
        return None
    counts = Counter(row.date.strftime("%Y-%m") for row in rows)
    return counts.most_common(1)[0][0]
