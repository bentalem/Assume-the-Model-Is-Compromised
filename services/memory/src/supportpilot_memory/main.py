"""The SupportPilot memory service.

A memory layer beside the agent, not inside the API — the way organisations deploy one (Mem0, Zep
and their peers sit next to an agent, not in its business service), and its own trust boundary. It
stores history, long-term memory and rules, and it assembles the context block an agent runtime
gives the model.

It differs from the memory products organisations usually plug in in one deliberate way. Those take
the user as a `user_id` parameter under one application-wide API key — one credential answering for
everyone, with identity as an argument. This service takes identity only from the user's verified
token, and asks the core database which organisation and roles that identity holds. Track 9 is
about why.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import context, history, memories, rules
from .config import Settings, load_settings
from .db import MemoryDatabase
from .errors import ApiError
from .observability import configure_logging, metrics
from .principal import PrincipalResolver
from .tokens import JwksCache, TokenVerifier
from .vectors import Embedder, VectorStore, parse_tenants

logger = logging.getLogger("supportpilot.memory")


@dataclass
class Services:
    settings: Settings
    db: MemoryDatabase
    principals: PrincipalResolver
    verifier: TokenVerifier
    # Phase 2 and 3 components attach here; see build_services.
    extras: dict[str, Any]


def build_services(settings: Settings) -> Services:
    extras: dict[str, Any] = {}
    if settings.tenants:
        extras["vectors"] = VectorStore(settings.qdrant_url, settings.qdrant_jwt_dir,
                                        parse_tenants(settings.tenants))
        extras["embedder"] = Embedder(settings.embeddings_url)
    return Services(
        settings=settings,
        db=MemoryDatabase(settings.mem_dsn),
        principals=PrincipalResolver(settings.core_dsn),
        verifier=TokenVerifier(
            issuer=settings.issuer,
            audience=settings.audience,
            jwks=JwksCache(settings.jwks_url),
            leeway_seconds=settings.token_leeway_seconds,
        ),
        extras=extras,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    services: Services = app.state.services
    services.db.open()
    services.principals.open()
    logger.info("memory_started", extra={"environment": services.settings.environment})
    try:
        yield
    finally:
        services.db.close()
        services.principals.close()
        for component in services.extras.values():
            component.close()


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or (services.settings if services else load_settings())
    configure_logging(settings.log_level)

    app = FastAPI(
        title="SupportPilot Memory",
        version="1.0.0",
        description=(
            "What the SupportPilot agent may remember, recall, forget and propose as a rule, on behalf "
            "of an authenticated support user. Every operation acts for the user in the verified "
            "token; none accepts a user, an organisation, a role or a source from the caller."
        ),
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment == "local" else None,
    )
    app.state.services = services or build_services(settings)

    # Model-facing: remember, recall, forget, propose_rule — the four operations in the memory action
    # document. Runtime-only (excluded from it): history, confirm, summaries, rule decisions and
    # retirement, and context assembly.
    app.include_router(memories.router)
    app.include_router(rules.router)
    app.include_router(history.router)
    app.include_router(context.router)

    # --------------------------------------------------------------------------------------------
    # Errors: {"error": {"code", "request_id"}}, and for a schema rejection the field and the kind of
    # failure — never the value. The API's rule, for the API's reasons: a rejected body is caller
    # content, and here it may be a sentence somebody wanted the agent to remember.
    # --------------------------------------------------------------------------------------------
    def _request_id(request: Request) -> str:
        raw = request.headers.get("x-request-id", "")
        cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in "-_")[:64]
        return cleaned or "mem-unassigned"

    def _error(status: int, code: str, request: Request, rejected: list | None = None) -> JSONResponse:
        error: dict = {"code": code, "request_id": _request_id(request)}
        if rejected:
            error["rejected"] = rejected
        return JSONResponse(status_code=status, content={"error": error},
                            headers={"X-Request-Id": _request_id(request)})

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        metrics.increment("supportpilot_memory_errors_total", code=exc.code)
        return _error(exc.status_code, exc.code, request)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        rejected = [
            {"field": ".".join(str(part) for part in error["loc"]), "error": error["type"]}
            for error in exc.errors()
        ][:10]
        logger.info("request_rejected", extra={"path": request.url.path, "rejected": rejected})
        return _error(400, "invalid_request", request, rejected)

    @app.exception_handler(psycopg.errors.InsufficientPrivilege)
    async def handle_store_refusal(request: Request, exc: Exception) -> JSONResponse:
        # A row-level security WITH CHECK refused a write. The store said no, and that is a decision
        # the caller should see as one — not an outage. Which policy refused stays in the log.
        logger.info("store_refused_write", extra={"path": request.url.path})
        return _error(403, "forbidden", request)

    @app.exception_handler(psycopg.errors.RaiseException)
    async def handle_trigger_refusal(request: Request, exc: Exception) -> JSONResponse:
        # A trigger refused the change — separation of duty on a rule decision.
        logger.info("store_refused_by_trigger", extra={"path": request.url.path})
        return _error(403, "forbidden", request)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", extra={"path": request.url.path}, exc_info=True)
        return _error(503, "unavailable", request)

    # --------------------------------------------------------------------------------------------
    # The memory action document — the four operations the model may call. The API's treatment,
    # for the API's reasons: a base URL Onyx can dispatch to, and no 422 response, because this
    # service never returns that shape (validation failures are 400 invalid_request).
    # --------------------------------------------------------------------------------------------
    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(
            title=app.title, version=app.version, description=app.description, routes=app.routes,
            servers=[{"url": settings.public_base_url,
                      "description": "SupportPilot memory on the internal application network"}],
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

    @app.middleware("http")
    async def count_requests(request: Request, call_next):
        response = await call_next(request)
        route = request.scope.get("route")
        metrics.increment("supportpilot_memory_requests_total",
                          route=getattr(route, "path", "unmatched"), method=request.method,
                          status=str(response.status_code))
        return response

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz() -> JSONResponse:
        services: Services = app.state.services
        checks = {"memory_db": services.db.healthy(), "identity": services.principals.healthy()}
        for name in ("vectors", "embedder"):
            if name in services.extras:
                checks[name] = services.extras[name].healthy()
        ready = all(checks.values())
        return JSONResponse(status_code=200 if ready else 503,
                            content={"status": "ready" if ready else "degraded", "checks": checks})

    return app


def run() -> None:  # pragma: no cover - container entry point
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8000, log_config=None)
