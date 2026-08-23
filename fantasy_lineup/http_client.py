"""Minimal on-demand HTTP client suitable for a Lambda runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    # Sportsbook edge endpoints reject urllib's TLS fingerprint. Keep this
    # optional so parser/unit-test users can run without native dependencies;
    # the deployment package installs it.
    from curl_cffi import requests as cffi_requests
except ImportError:  # pragma: no cover - exercised only in minimal installs
    cffi_requests = None


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]


class HttpClient:
    def __init__(
        self,
        timeout_seconds: float = 5.0,
        user_agent: str = "nfl-fantasy-lineup/0.1",
        impersonate: str = "chrome120",
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.impersonate = impersonate

    def get(self, url: str) -> HttpResponse:
        headers = {"User-Agent": self.user_agent, "Accept": "text/html,application/json"}
        if cffi_requests is not None:
            try:
                response = cffi_requests.get(
                    url,
                    headers=headers,
                    impersonate=self.impersonate,
                    timeout=self.timeout_seconds,
                )
                if response.status_code >= 400:
                    raise RuntimeError(f"Sportsbook request failed with HTTP {response.status_code}: {url}")
                return HttpResponse(response.status_code, response.content, dict(response.headers.items()))
            except RuntimeError:
                raise
            except Exception as exc:
                raise RuntimeError(f"Sportsbook request failed: {url} ({exc})") from exc

        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return HttpResponse(response.status, response.read(), dict(response.headers.items()))
        except HTTPError as exc:
            raise RuntimeError(f"Sportsbook request failed with HTTP {exc.code}: {url}") from exc
        except URLError as exc:
            raise RuntimeError(f"Sportsbook request failed: {url} ({exc.reason})") from exc


def decode_json(response: HttpResponse) -> object:
    try:
        return json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Sportsbook response was not valid UTF-8 JSON") from exc
