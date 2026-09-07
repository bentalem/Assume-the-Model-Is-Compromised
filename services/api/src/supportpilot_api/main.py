"""SupportPilot API application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .audit.writer import AuditWriter
from .auth.tokens import JwksCache, TokenVerifier
from .config import Settings, load_settings
from .db import Database
from .errors import ApiError
from .pipeline import Pipeline
from .policy.client import PolicyClient
from .repositories.memberships import MembershipRepository
from .repositories.actions import ActionRepository
from .repositories.notes import NoteRepository
from .repositories.customers import CustomerRepository
from .repositories.orders import OrderRepository
from .repositories.tickets import TicketRepository
from .tools import customers as customers_tool
from .internal import approvals as approvals_router
from .tools import actions as actions_tool
from .tools import notes as notes_tool
from .tools import orders as orders_tool
from .tools import tickets as tickets_tool

logger = logging.getLogger("supportpilot")


@dataclass
class Services:
    settings: Settings
    database: Database
    verifier: TokenVerifier
    policy: PolicyClient
    memberships: MembershipRepository
    orders: OrderRepository
    customers: CustomerRepository
    tickets: TicketRepository
    notes: NoteRepository
    actions: ActionRepository
    pipeline: Pipeline


def build_services(settings: Settings) -> Services:
    database = Database(settings.dsn)
    policy = PolicyClient(settings.opa_url, timeout_ms=settings.opa_timeout_ms)
    verifier = TokenVerifier(
        issuer=settings.issuer,
        audience=settings.audience,
        jwks=JwksCache(settings.jwks_url),
        leeway_seconds=settings.token_leeway_seconds,
    )
    audit = AuditWriter(database)
    return Services(
        settings=settings,
        database=database,
        verifier=verifier,
        policy=policy,
        memberships=MembershipRepository(database),
        orders=OrderRepository(database),
        customers=CustomerRepository(database),
        tickets=TicketRepository(database),
        notes=NoteRepository(database, audit),
        actions=ActionRepository(database, audit),
        pipeline=Pipeline(policy, audit),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    services: Services = app.state.services
    services.database.open()
    logger.info("api_started", extra={"environment": services.settings.environment})
    try:
        yield
    finally:
        services.database.close()
        services.policy.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(
        title="SupportPilot Actions",
        version="1.0.0",
        description=(
            "Business operations the SupportPilot agent may request on behalf of an authenticated "
            "support user. Every operation authorizes the individual user; none accepts an identity "
            "supplied by the caller."
        ),
        lifespan=lifespan,
        # Docs are off by default: the action document is exported deliberately and reviewed, not
        # served from a running service.
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment == "local" else None,
    )
    app.state.services = build_services(settings)

    app.include_router(orders_tool.router)
    app.include_router(customers_tool.router)
    app.include_router(tickets_tool.router)
    app.include_router(notes_tool.router)
    app.include_router(actions_tool.router)
    # Not a tool: /internal is excluded from the action document and never registered
    # with Onyx, so the model has no route to approval.
    app.include_router(approvals_router.router)

    # --------------------------------------------------------------------------------------------
    # Error handling. Every response body is {"error": {"code", "request_id"}} and nothing else.
    # --------------------------------------------------------------------------------------------
    def _request_id(request: Request) -> str:
        raw = request.headers.get("x-request-id", "")
        cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in "-_")[:64]
        return cleaned or "req-unassigned"

    def _error(status: int, code: str, request: Request) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "request_id": _request_id(request)}},
            headers={"X-Request-Id": _request_id(request)},
        )

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status_code, exc.code, request)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # The default handler echoes the offending value and the field path. Both are dropped:
        # a schema violation reveals nothing beyond "invalid_request" (T-007).
        logger.info("request_rejected", extra={"path": request.url.path})
        return _error(400, "invalid_request", request)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", extra={"path": request.url.path}, exc_info=True)
        return _error(503, "unavailable", request)

    # --------------------------------------------------------------------------------------------
    # The action document.
    #
    # FastAPI adds a 422 response with its HTTPValidationError schema to every route that has
    # parameters. This API never returns that shape — handle_validation_error converts it to
    # 400 invalid_request — so advertising it would describe a response that cannot occur and would
    # publish the internal field-path structure of the error to the model. Both are removed.
    # --------------------------------------------------------------------------------------------
    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        for path in schema.get("paths", {}).values():
            for operation in path.values():
                if isinstance(operation, dict):
                    operation.get("responses", {}).pop("422", None)

        for name in ("HTTPValidationError", "ValidationError"):
            schema.get("components", {}).get("schemas", {}).pop(name, None)

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

    # --------------------------------------------------------------------------------------------
    # Health. Not part of the action document; reachable only on the internal network.
    # --------------------------------------------------------------------------------------------
    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz() -> JSONResponse:
        services: Services = app.state.services
        checks = {
            "database": services.database.healthy(),
            "policy": services.policy.healthy(),
        }
        ready = all(checks.values())
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "degraded", "checks": checks},
        )

    return app


app = create_app if __name__ == "__main__" else None


def run() -> None:  # pragma: no cover - container entry point
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8000, log_config=None)
