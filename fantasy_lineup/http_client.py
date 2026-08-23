"""Minimal on-demand HTTP client suitable for a Lambda runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]


class HttpClient:
    def __init__(self, timeout_seconds: float = 5.0, user_agent: str = "nfl-fantasy-lineup/0.1") -> None:
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def get(self, url: str) -> HttpResponse:
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "text/html,application/json"})
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
