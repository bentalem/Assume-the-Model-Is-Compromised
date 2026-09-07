"""Approval portal.

The portal has no database credential and no route to PostgreSQL or OPA. Every fact it shows comes
from the API, and every decision it records goes through the API. That is deliberate: a portal that
could reach the database could change an approved payload, which is the one thing approval exists to
prevent.

What it must show, from SP-BUILD-001 §9: action type, requester, organization, resource, amount,
destination, reason, risk level, expiration — and the exact immutable payload that will execute,
alongside the hash the approval binds to.
"""

from __future__ import annotations

import html
import logging
import os

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger("supportpilot.approval")

API_URL = os.environ.get("SUPPORTPILOT_API_URL", "http://api:8000")

app = FastAPI(
    title="SupportPilot Approval Portal",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

_STYLE = """
<style>
  :root { color-scheme: light dark; }
  body { font: 15px/1.5 system-ui, sans-serif; margin: 0; background: #f6f7f9; color: #16181d; }
  main { max-width: 780px; margin: 0 auto; padding: 32px 20px 64px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: #667085; margin: 0 0 28px; }
  .card { background: #fff; border: 1px solid #e3e6ea; border-radius: 8px; padding: 20px;
          margin-bottom: 16px; }
  dl { display: grid; grid-template-columns: 190px 1fr; gap: 8px 16px; margin: 0; }
  dt { color: #667085; }
  dd { margin: 0; font-variant-numeric: tabular-nums; }
  .amount { font-size: 20px; font-weight: 600; }
  pre { background: #f2f4f7; border: 1px solid #e3e6ea; border-radius: 6px; padding: 12px;
        overflow-x: auto; font: 12px/1.5 ui-monospace, monospace; margin: 8px 0 0; }
  .hash { font: 12px ui-monospace, monospace; color: #475467; word-break: break-all; }
  .warn { background: #fff8e6; border-color: #f0c36d; }
  .warn strong { color: #8a5a00; }
  form { display: inline; }
  button { font: inherit; padding: 9px 18px; border-radius: 6px; border: 1px solid transparent;
           cursor: pointer; }
  .approve { background: #0a7d33; color: #fff; }
  .reject { background: #fff; color: #b42318; border-color: #d0d5dd; margin-left: 8px; }
  .empty { color: #667085; }
  a { color: #175cd3; }
</style>
"""


def _page(title: str, body: str) -> str:
    return f"<!doctype html><meta charset='utf-8'><title>{html.escape(title)}</title>{_STYLE}<main>{body}</main>"


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request) -> HTMLResponse:
    return HTMLResponse(
        _page(
            "SupportPilot Approvals",
            "<h1>SupportPilot approval portal</h1>"
            "<p class='sub'>Independent review of sensitive actions.</p>"
            "<div class='card'>"
            "<p>Open a pending action directly: <code>/actions/&lt;action_id&gt;</code></p>"
            "<p class='sub'>Sign-in is handled by Keycloak; this build expects an approver token "
            "supplied by the reverse proxy. Until that is wired, the review screen is reachable "
            "with a bearer token in the Authorization header.</p>"
            "</div>",
        )
    )


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


@app.get("/actions/{action_id}", response_class=HTMLResponse, include_in_schema=False)
def review(request: Request, action_id: str) -> HTMLResponse:
    token = _bearer(request)
    if not token:
        return HTMLResponse(
            _page("Sign in required", "<div class='card'><p>An approver token is required.</p></div>"),
            status_code=401,
        )

    try:
        response = httpx.get(
            f"{API_URL}/internal/approvals/{action_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
    except httpx.HTTPError:
        return HTMLResponse(
            _page("Unavailable", "<div class='card'><p>The action service is unavailable.</p></div>"),
            status_code=503,
        )

    if response.status_code != 200:
        return HTMLResponse(
            _page(
                "Not available",
                "<div class='card'><p>This action is not available for review.</p></div>",
            ),
            status_code=response.status_code,
        )

    action = response.json()
    e = html.escape

    # The exact payload that will execute, and the hash the approval binds to. If either changes,
    # the approval is void — the worker recomputes the hash before it calls a provider.
    payload_json = e(action["payload_canonical"])

    body = f"""
    <h1>Review refund request</h1>
    <p class='sub'>Approving this authorises the exact payload below, and nothing else.</p>

    <div class='card'>
      <dl>
        <dt>Action</dt><dd>{e(action['action_type'])}</dd>
        <dt>Requested by</dt><dd>{e(action['requester_name'])}</dd>
        <dt>Organization</dt><dd>{e(action['organization'])}</dd>
        <dt>Resource</dt><dd>{e(action['resource_id'])}</dd>
        <dt>Amount</dt><dd class='amount'>{e(action['amount'])} {e(action['currency'])}</dd>
        <dt>Reason</dt><dd>{e(action['reason'])}</dd>
        <dt>Risk level</dt><dd>{e(action['risk_level'])}</dd>
        <dt>State</dt><dd>{e(action['state'])}</dd>
        <dt>Expires</dt><dd>{e(action['expires_at'])}</dd>
      </dl>
    </div>

    <div class='card'>
      <strong>Exact payload to execute</strong>
      <pre>{payload_json}</pre>
      <p class='hash'>sha256 {e(action['payload_hash'])}</p>
    </div>

    <div class='card warn'>
      <strong>Separation of duty.</strong> You cannot approve an action you requested. Approval is
      recorded against your identity and the payload hash above, and expires at the time shown.
    </div>

    <div class='card'>
      <form method='post' action='/actions/{e(action_id)}/decide'>
        <input type='hidden' name='decision' value='approved'>
        <input type='hidden' name='approved_hash' value='{e(action['payload_hash'])}'>
        <button class='approve' type='submit'>Approve this exact payload</button>
      </form>
      <form method='post' action='/actions/{e(action_id)}/decide'>
        <input type='hidden' name='decision' value='rejected'>
        <input type='hidden' name='approved_hash' value='{e(action['payload_hash'])}'>
        <button class='reject' type='submit'>Reject</button>
      </form>
    </div>
    """
    return HTMLResponse(_page("Review refund request", body))


@app.post("/actions/{action_id}/decide", include_in_schema=False)
def decide(
    request: Request,
    action_id: str,
    decision: str = Form(...),
    approved_hash: str = Form(...),
    comment: str | None = Form(default=None),
) -> HTMLResponse:
    token = _bearer(request)
    if not token:
        return HTMLResponse(
            _page("Sign in required", "<div class='card'><p>An approver token is required.</p></div>"),
            status_code=401,
        )

    # The portal forwards the hash it displayed. The API compares it against the stored hash and
    # refuses a mismatch, so a stale screen cannot approve a payload that has since changed.
    response = httpx.post(
        f"{API_URL}/internal/approvals/{action_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"decision": decision, "approved_hash": approved_hash, "comment": comment},
        timeout=15,
    )

    if response.status_code in (200, 201):
        return HTMLResponse(
            _page(
                "Decision recorded",
                f"<div class='card'><h1>Decision recorded</h1>"
                f"<p>The action was <strong>{html.escape(decision)}</strong>. "
                f"Execution, if approved, is performed by the worker.</p></div>",
            )
        )

    reason = {
        409: "A decision already exists for this action.",
        403: "You are not permitted to decide this action.",
        404: "This action is not available.",
        422: "The payload changed since this screen was loaded. Reload and review again.",
    }.get(response.status_code, "The decision could not be recorded.")

    return HTMLResponse(
        _page("Not recorded", f"<div class='card warn'><p>{html.escape(reason)}</p></div>"),
        status_code=response.status_code,
    )


def run() -> None:  # pragma: no cover - container entry point
    import uvicorn

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    uvicorn.run(app, host="0.0.0.0", port=8090, log_config=None)
