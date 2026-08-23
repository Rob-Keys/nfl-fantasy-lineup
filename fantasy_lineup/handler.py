"""AWS API Gateway/Lambda entry point."""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import os
from typing import Any

from .service import FantasyLineupService


class MethodNotAllowedError(ValueError):
    """Raised when an API Gateway request is not a POST request."""


class UnauthorizedError(ValueError):
    """Raised when a request did not come through the trusted edge function."""


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        require_post_method(event)
        require_edge_secret(event)
        request = parse_event_body(event)
        response = FantasyLineupService().generate(request)
        return api_response(200, response.to_dict())
    except MethodNotAllowedError as exc:
        return api_response(405, {"error": str(exc)})
    except UnauthorizedError as exc:
        return api_response(401, {"error": str(exc)})
    except (ValueError, NotImplementedError) as exc:
        return api_response(400, {"error": str(exc)})
    except Exception:
        # Do not return internal exception details to API callers.
        return api_response(500, {"error": "Internal server error"})


def require_post_method(event: dict[str, Any]) -> None:
    """Require POST in an API Gateway HTTP API v2 event."""
    request_context = event.get("requestContext")
    http = request_context.get("http") if isinstance(request_context, dict) else None
    method = http.get("method") if isinstance(http, dict) else None
    if not isinstance(method, str) or method.upper() != "POST":
        raise MethodNotAllowedError("Only POST requests are supported")


def require_edge_secret(event: dict[str, Any]) -> None:
    """Require the secret injected by the Cloudflare Pages Function proxy.

    The secret is intentionally checked in Lambda rather than relying on CORS.
    CORS only affects browsers; this check also blocks direct API Gateway calls
    that do not know the server-side secret.
    """
    expected = os.environ.get("BACKEND_SHARED_SECRET")
    if not expected:
        raise UnauthorizedError("Backend edge authorization is not configured")

    headers = event.get("headers")
    if not isinstance(headers, dict):
        raise UnauthorizedError("Unauthorized")

    supplied = None
    for name, value in headers.items():
        if isinstance(name, str) and name.lower() == "x-internal-api-key":
            supplied = value
            break

    if not isinstance(supplied, str) or not hmac.compare_digest(supplied, expected):
        raise UnauthorizedError("Unauthorized")


def parse_event_body(event: dict[str, Any]) -> dict[str, Any]:
    if "body" not in event:
        raise ValueError("Request body is required")
    body = event["body"]
    if isinstance(body, str):
        if event.get("isBase64Encoded"):
            try:
                body = base64.b64decode(body, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError) as exc:
                raise ValueError("Request body was not valid base64 UTF-8") from exc
        try:
            body = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON") from exc
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    return body


def api_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
