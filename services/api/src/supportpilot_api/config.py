"""Runtime configuration.

Secrets are read from mounted files, never from environment variables, so they do not appear in
`docker inspect`, crash dumps, or a child process environment (SP-DATA-001 §10).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised at startup when configuration is missing or unusable."""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"required setting {name} is not set")
    return value


def _read_secret_file(name: str) -> str:
    path = Path(_require(name))
    try:
        secret = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read secret file for {name}") from exc
    secret = secret.strip("\r\n")
    if not secret:
        raise ConfigError(f"secret file for {name} is empty")
    return secret


@dataclass(frozen=True)
class Settings:
    environment: str

    # Identity
    issuer: str
    jwks_url: str
    audience: str
    token_leeway_seconds: int

    # Policy
    opa_url: str
    opa_timeout_ms: int

    # Database
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)

    log_level: str = "INFO"

    @property
    def dsn(self) -> str:
        # application_name makes every connection identifiable in pg_stat_activity
        # (SP-DATA-001 §5, "Every connection sets a clear application_name").
        return (
            f"host={self.db_host} port={self.db_port} dbname={self.db_name} "
            f"user={self.db_user} password={self.db_password} "
            f"application_name=supportpilot-api"
        )

    def __repr__(self) -> str:  # pragma: no cover - defensive
        # Never let a settings object print a credential into a log or traceback.
        return (
            f"Settings(environment={self.environment!r}, issuer={self.issuer!r}, "
            f"audience={self.audience!r}, db_host={self.db_host!r}, db_user={self.db_user!r})"
        )


def load_settings() -> Settings:
    return Settings(
        environment=os.environ.get("SUPPORTPILOT_ENV", "local"),
        issuer=_require("KEYCLOAK_ISSUER"),
        jwks_url=_require("KEYCLOAK_JWKS_URL"),
        audience=_require("SUPPORTPILOT_AUDIENCE"),
        token_leeway_seconds=int(os.environ.get("TOKEN_LEEWAY_SECONDS", "30")),
        opa_url=_require("OPA_URL"),
        opa_timeout_ms=int(os.environ.get("OPA_TIMEOUT_MS", "250")),
        db_host=_require("DATABASE_HOST"),
        db_port=int(os.environ.get("DATABASE_PORT", "5432")),
        db_name=_require("DATABASE_NAME"),
        db_user=_require("DATABASE_USER"),
        db_password=_read_secret_file("API_DATABASE_SECRET_FILE"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
