"""The API error model.

Error bodies carry a stable code and the request id — never schema names, SQL, resource details, or
policy internals (SP-DATA-001 §8, "Database errors are mapped to stable API errors without
returning schema details").

The most important rule here is `not_found` for a cross-tenant request. A 403 would confirm that the
resource exists in another tenant; 404 is indistinguishable from an unknown identifier.
"""

from __future__ import annotations

from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(status_code=status_code, detail=code)
        self.code = code


def invalid_request() -> ApiError:
    return ApiError(400, "invalid_request")


def unauthenticated() -> ApiError:
    return ApiError(401, "unauthenticated")


def forbidden() -> ApiError:
    return ApiError(403, "forbidden")


def not_found() -> ApiError:
    """Unknown resource, or a resource the caller may not see. Deliberately identical."""
    return ApiError(404, "not_found")


def conflict() -> ApiError:
    return ApiError(409, "conflict")


def business_rule() -> ApiError:
    return ApiError(422, "business_rule")


def rate_limited() -> ApiError:
    return ApiError(429, "rate_limited")


def unavailable() -> ApiError:
    return ApiError(503, "unavailable")
