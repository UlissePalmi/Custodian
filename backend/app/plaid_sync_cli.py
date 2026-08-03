"""Entrypoint for the `custodian-plaid-sync` systemd timer.

    .venv/bin/python -m app.plaid_sync_cli

Syncs every linked Plaid item and exits 0 regardless of per-item failures
(those are recorded on the `PlaidItem` row itself, see `services.plaid_sync`)
so a single broken connection doesn't fail the whole timer run.
"""

import sys

from app.database import SessionLocal
from app.services.plaid_sync import sync_all_items


def main() -> int:
    with SessionLocal() as db:
        results = sync_all_items(db)
    total_imported = sum(r.imported_count for r in results)
    print(f"Plaid sync: {len(results)} batch(es), {total_imported} transaction(s) imported.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
