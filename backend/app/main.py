from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import register_error_handlers
from app.routers import categories, chase_import, months, portfolio, transactions, yearly


def create_app() -> FastAPI:
    app = FastAPI(title="Custodian", version="0.1.0")

    # This service is the API only; the front end runs separately on its own
    # port, so every browser request to it is cross-origin. The regex matches
    # that port on any host, which covers localhost, the Pi's LAN address and a
    # Tailscale name without keeping a list of them. No cookies or auth headers
    # are sent, so credentials stay off.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    app.include_router(categories.router)
    app.include_router(months.router)
    app.include_router(transactions.router)
    app.include_router(yearly.router)
    app.include_router(portfolio.router)
    app.include_router(chase_import.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
