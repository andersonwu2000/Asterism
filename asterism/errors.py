"""The one error type the domain raises. Every entrance turns it into its own shape:
JSON {error, message} with a status, an MCP tool error, or a page."""
from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def bad_request(code: str, message: str) -> ApiError:
    return ApiError(400, code, message)


def not_signed_in() -> ApiError:
    return ApiError(401, "not_signed_in", "Sign in first.")


def invalid_credential() -> ApiError:
    return ApiError(401, "invalid_credential",
                    "This credential is revoked or unknown. Ask your person to authorise this computer "
                    "again by running the helper with --join.")


def forbidden(message: str) -> ApiError:
    return ApiError(403, "forbidden", message)


def not_found(message: str) -> ApiError:
    return ApiError(404, "not_found", message)


def gone(message: str) -> ApiError:
    return ApiError(410, "gone", message)


def conflict(message: str) -> ApiError:
    return ApiError(409, "conflict", message)
