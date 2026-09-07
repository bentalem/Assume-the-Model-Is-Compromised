"""Approval portal.

Phase 4 builds the real review and decision screens (P4-08 … P4-10). The service exists now so the
network boundary is real from the start: it sits on `edge` and `app`, and has **no** database
credential and **no** route to PostgreSQL or OPA. Every fact it displays comes from the API, and
every decision it records goes through the API.

That shape is the point. A portal that could reach the database could modify an approved payload.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

logger = logging.getLogger("supportpilot.approval")

app = FastAPI(
    title="SupportPilot Approval Portal",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return (
        "<!doctype html><meta charset='utf-8'><title>SupportPilot Approvals</title>"
        "<h1>SupportPilot approval portal</h1>"
        "<p>No approval workflow is deployed yet. Refund proposals, independent approval, and the "
        "immutable payload view arrive in phase 4.</p>"
    )


def run() -> None:  # pragma: no cover - container entry point
    import uvicorn

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    uvicorn.run(app, host="0.0.0.0", port=8090, log_config=None)
