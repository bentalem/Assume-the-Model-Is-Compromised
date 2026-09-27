"""Runtime configuration for the memory service.

Secrets are read from mounted files, never from environment variables, so they do not appear in
`docker inspect`, a crash dump or a child process's environment — the same rule the API follows.
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


def read_secret_file(name: str) -> str:
    """Read the secret whose *path* is in environment variable `name`."""
    path = Path(_require(name))
    try:
        secret = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read secret file for {name}") from exc
    secret = secret.strip("\r\n")
    if not secret:
        raise ConfigError(f"secret file for {name} is empty")
    return secret


def _optional_secret_file(name: str) -> str:
    return read_secret_file(name) if os.environ.get(name, "").strip() else ""


@dataclass(frozen=True)
class Settings:
    environment: str

    # Identity. The audience is the memory service's own, never the API's: a token minted for one
    # resource server is not a token for another — challenge 1.2, applied here.
    issuer: str
    jwks_url: str
    audience: str
    token_leeway_seconds: int

    # memory-db, as mem_service_role.
    mem_db_host: str
    mem_db_port: int
    mem_db_name: str
    mem_db_user: str
    mem_db_password: str = field(repr=False)

    # The core database, as sp_memory_lookup_role — which may call app.resolve_subject and nothing
    # else. This is how the memory service learns a caller's organisation and roles.
    core_db_host: str = "postgres"
    core_db_port: int = 5432
    core_db_name: str = "supportpilot"
    core_db_user: str = "sp_memory_lookup_role"
    core_db_password: str = field(default="", repr=False)

    # Qdrant and the embedding model (phase 2). Per-tenant credentials are read from files whose
    # directory is configured, so adding a tenant is a new file rather than a code change.
    qdrant_url: str = "http://qdrant:6333"
    qdrant_jwt_dir: str = "/run/secrets"
    embeddings_url: str = "http://embeddings:80"
    # org_id:slug pairs — the organisations this deployment has a per-tenant collection for.
    tenants: str = ""

    public_base_url: str = "http://memory:8000"
    log_level: str = "INFO"

    @property
    def mem_dsn(self) -> str:
        return (
            f"host={self.mem_db_host} port={self.mem_db_port} dbname={self.mem_db_name} "
            f"user={self.mem_db_user} password={self.mem_db_password} "
            f"application_name=supportpilot-memory"
        )

    @property
    def core_dsn(self) -> str:
        return (
            f"host={self.core_db_host} port={self.core_db_port} dbname={self.core_db_name} "
            f"user={self.core_db_user} password={self.core_db_password} "
            f"application_name=supportpilot-memory-lookup"
        )

    def __repr__(self) -> str:  # pragma: no cover - defensive
        # Never let a settings object print a credential into a log or a traceback.
        return (
            f"Settings(environment={self.environment!r}, issuer={self.issuer!r}, "
            f"audience={self.audience!r}, mem_db_host={self.mem_db_host!r})"
        )


def load_settings() -> Settings:
    return Settings(
        environment=os.environ.get("SUPPORTPILOT_ENV", "local"),
        issuer=_require("KEYCLOAK_ISSUER"),
        jwks_url=_require("KEYCLOAK_JWKS_URL"),
        audience=_require("MEMORY_AUDIENCE"),
        token_leeway_seconds=int(os.environ.get("TOKEN_LEEWAY_SECONDS", "30")),
        mem_db_host=_require("MEMORY_DB_HOST"),
        mem_db_port=int(os.environ.get("MEMORY_DB_PORT", "5432")),
        mem_db_name=_require("MEMORY_DB_NAME"),
        mem_db_user=_require("MEMORY_DB_USER"),
        mem_db_password=read_secret_file("MEMORY_DB_SECRET_FILE"),
        core_db_host=os.environ.get("CORE_DB_HOST", "postgres"),
        core_db_port=int(os.environ.get("CORE_DB_PORT", "5432")),
        core_db_name=os.environ.get("CORE_DB_NAME", "supportpilot"),
        core_db_user=os.environ.get("CORE_DB_USER", "sp_memory_lookup_role"),
        core_db_password=read_secret_file("CORE_DB_SECRET_FILE"),
        qdrant_url=os.environ.get("QDRANT_URL", "http://qdrant:6333"),
        qdrant_jwt_dir=os.environ.get("QDRANT_JWT_DIR", "/run/secrets"),
        embeddings_url=os.environ.get("EMBEDDINGS_URL", "http://embeddings:80"),
        tenants=os.environ.get("MEMORY_TENANTS", ""),
        public_base_url=os.environ.get("MEMORY_PUBLIC_BASE_URL", "http://memory:8000"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
