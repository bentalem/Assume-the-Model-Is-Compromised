"""The delegation broker.

Architecture C — passthrough — hands an agent the user's whole token, whatever the task. This
service is architecture D: an agent gets a token that names the user *and* the agent, and carries
only what the call in front of it needs. Four endpoints:

  /{profile}/v1/...        The gateway. An agent platform registered with a profile's action
                           document calls the API through here. Verify the user's token, resolve
                           the operation from method and path, look up the scope it needs, refuse
                           it if the profile's ceiling does not include it, mint a token for exactly
                           that scope, forward. The profile in the path is not an authentication:
                           the caller already holds the user's whole token, and everything the
                           gateway can do with it is narrower than what the caller already has.
  POST /oauth/token        RFC 8693 token exchange, for an agent — or a sub-agent — that holds its
                           own credential. See exchange.py for the rules.
  /.well-known/jwks.json   The public key the API verifies minted tokens with.
  /healthz

What the broker decides is bounded by trusted configuration (trusted.py) and nothing in a request.
What it cannot decide is anything the API decides: roles still come from the database, the policy
still runs, and a delegated token is a limit on top of those, never a source of them.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from . import operations
from .exchange import exchange
from .tokens import KeycloakKeys, Minter, SigningKey, TokenRefused, UserVerifier
from .trusted import (
    ConfigurationRefused,
    Profile,
    ScopeTable,
    load_profiles,
    load_scopes,
    read_settings,
)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("supportpilot.broker")

#: A gateway token lives for one forwarded call; sixty seconds covers a slow API and nothing more.
GATEWAY_LIFETIME_SECONDS = 60
_MAX_BODY_BYTES = 64 * 1024


@dataclass
class Broker:
    scopes: ScopeTable
    profiles: dict[str, Profile]
    users: UserVerifier
    minter: Minter
    signing_key: SigningKey
    api_url: str
    settings_path: Path
    #: Tests replace the API with an in-process one. None means the real network.
    transport: httpx.AsyncBaseTransport | None = None

    def settings(self) -> dict[str, bool]:
        return read_settings(self.settings_path)


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        raise ConfigurationRefused(f"required setting {name} is not set")
    return value


def build() -> Broker:
    scopes = load_scopes(Path(_env("BROKER_SCOPES_FILE", "/etc/broker/scopes.json")))
    profiles = load_profiles(
        Path(_env("BROKER_PROFILES_FILE", "/etc/broker/profiles.json")),
        Path(_env("BROKER_SECRETS_DIR", "/run/secrets")),
        scopes,
    )
    key_file = Path(_env("BROKER_SIGNING_KEY_FILE", "/run/secrets/broker_signing_key"))
    try:
        signing_key = SigningKey(key_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ConfigurationRefused(f"signing key unreadable: {type(exc).__name__}") from exc
    audience = _env("SUPPORTPILOT_AUDIENCE", "supportpilot-api")
    return Broker(
        scopes=scopes,
        profiles=profiles,
        users=UserVerifier(
            issuer=_env("KEYCLOAK_ISSUER"),
            audience=audience,
            keys=KeycloakKeys(_env("KEYCLOAK_JWKS_URL")),
        ),
        minter=Minter(signing_key, issuer=_env("BROKER_ISSUER", "http://broker:8097"),
                      audience=audience),
        signing_key=signing_key,
        api_url=_env("SUPPORTPILOT_API_URL", "http://api:8000"),
        settings_path=Path(_env("BROKER_SETTINGS_FILE", "/broker-settings/settings.json")),
    )


def create_app(broker: Broker) -> FastAPI:
    app = FastAPI(title="SupportPilot delegation broker", version="1.0.0",
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.broker = broker

    @app.get("/healthz")
    def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok", "profiles": sorted(broker.profiles)})

    @app.get("/.well-known/jwks.json")
    def jwks() -> JSONResponse:
        return JSONResponse(broker.signing_key.jwks())

    @app.post("/oauth/token")
    async def token(request: Request) -> JSONResponse:
        if request.headers.get("content-type", "").split(";")[0].strip() != \
                "application/x-www-form-urlencoded":
            return _oauth_error(400, "invalid_request")
        raw = await request.body()
        if len(raw) > _MAX_BODY_BYTES:
            return _oauth_error(400, "invalid_request")
        try:
            parsed = parse_qs(raw.decode("utf-8"), keep_blank_values=True, strict_parsing=False)
        except UnicodeDecodeError:
            return _oauth_error(400, "invalid_request")
        # A parameter sent twice is refused rather than resolved: RFC 6749 §3.2.
        if any(len(values) > 1 for values in parsed.values()):
            return _oauth_error(400, "invalid_request")
        form = {k: v[0] for k, v in parsed.items()}
        client = _authenticate_client(broker, request, form)
        outcome = exchange(form, client=client, scopes=broker.scopes, settings=broker.settings(),
                           users=broker.users, minter=broker.minter)
        return JSONResponse(outcome.body, status_code=outcome.status,
                            headers={"Cache-Control": "no-store", "Pragma": "no-cache"})

    @app.api_route("/{profile}/v1/{rest:path}", methods=["GET", "POST"])
    async def gateway(profile: str, rest: str, request: Request) -> Response:
        return await _gateway(broker, profile, "/v1/" + rest, request)

    return app


def _oauth_error(status: int, code: str) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status, headers={"Cache-Control": "no-store"})


def _api_error(status: int, code: str) -> JSONResponse:
    # The API's own error shape, so a caller of the gateway handles one shape, not two.
    return JSONResponse({"error": {"code": code}}, status_code=status)


def _authenticate_client(broker: Broker, request: Request, form: dict[str, str]) -> Profile | None:
    """client_secret_basic or client_secret_post; either way, the profile's own credential."""
    client_id, secret = form.get("client_id", ""), form.get("client_secret", "")
    header = request.headers.get("authorization", "")
    if header.lower().startswith("basic "):
        try:
            client_id, _, secret = base64.b64decode(header[6:]).decode("utf-8").partition(":")
        except (binascii.Error, UnicodeDecodeError):
            return None
    profile = broker.profiles.get(client_id)
    return profile if profile is not None and profile.authenticates(secret) else None


async def _gateway(broker: Broker, profile_name: str, path: str, request: Request) -> Response:
    profile = broker.profiles.get(profile_name)
    if profile is None:
        return _api_error(404, "unknown_profile")

    operation = operations.resolve(request.method, path)
    if operation is None:
        return _api_error(404, "unknown_operation")

    authorization = request.headers.get("authorization", "")
    scheme, _, user_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not user_token.strip():
        return _api_error(401, "unauthenticated")
    try:
        user = broker.users.verify(user_token.strip())
    except TokenRefused as refused:
        logger.info("gateway_refused", extra={"reason": refused.reason, "profile": profile.name})
        return _api_error(401, "unauthenticated")

    settings = broker.settings()
    if settings["broker.passthrough"]:
        # "So it just works." The user's whole token goes to the API, the agent disappears from the
        # audit trail, and the profile's ceiling limits nothing. Architecture C, reached by a switch.
        forward_token, delegation = user_token.strip(), "passthrough"
        logger.warning("gateway_passthrough", extra={"profile": profile.name,
                                                     "operation": operation.operation_id})
    else:
        needed = broker.scopes.for_action(operation.action)
        if needed is None or needed in broker.scopes.never_delegable or needed not in profile.ceiling:
            logger.info("gateway_refused", extra={"reason": "scope_exceeds_profile",
                                                  "profile": profile.name,
                                                  "operation": operation.operation_id})
            return _api_error(403, "scope_exceeds_profile")
        forward_token, claims = broker.minter.mint(
            subject=user.subject, act={"sub": profile.name}, scopes=frozenset({needed}),
            lifetime_seconds=GATEWAY_LIFETIME_SECONDS, not_after=user.expires_at, acr=user.acr,
        )
        delegation = (f"minted; actor={profile.name}; scope={needed}; "
                      f"expires_in={claims['exp'] - claims['iat']}")

    body = await request.body()
    if len(body) > _MAX_BODY_BYTES:
        return _api_error(413, "invalid_request")
    headers = {"Authorization": f"Bearer {forward_token}"}
    if body:
        headers["Content-Type"] = request.headers.get("content-type", "application/json")
    if request_id := request.headers.get("x-request-id"):
        headers["X-Request-Id"] = request_id[:128]

    query = request.url.query
    url = f"{broker.api_url}{path}" + (f"?{query}" if query else "")
    try:
        async with httpx.AsyncClient(timeout=30, transport=broker.transport) as client:
            upstream = await client.request(request.method, url, headers=headers, content=body)
    except httpx.HTTPError:
        logger.warning("gateway_upstream_unreachable", extra={"operation": operation.operation_id})
        return _api_error(503, "unavailable")

    passed = {"X-Delegation": delegation}
    for name in ("content-type", "x-request-id"):
        if name in upstream.headers:
            passed[name] = upstream.headers[name]
    return Response(content=upstream.content, status_code=upstream.status_code, headers=passed)


def run() -> None:
    import uvicorn

    try:
        broker = build()
    except ConfigurationRefused as exc:
        print(f"broker: {exc}", file=sys.stderr)
        raise SystemExit(78)  # EX_CONFIG
    logger.info("broker ready: profiles %s", ", ".join(
        f"{p.name}={sorted(p.ceiling)}" for p in broker.profiles.values()))
    uvicorn.run(
        create_app(broker),
        host="0.0.0.0",  # noqa: S104 — never published; reachable only on the internal `app` network
        port=int(os.environ.get("PORT", "8097")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
