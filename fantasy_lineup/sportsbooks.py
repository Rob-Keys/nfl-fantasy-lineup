"""Sportsbook interfaces and deliberately isolated parser stubs.

The public URLs and page/API schemas change frequently. Each adapter makes a
fresh request for exactly one requested player, then delegates parsing to a
small method that can be implemented from the current sportsbook layout.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable
from urllib.parse import quote

from .config import STATS_BY_POSITION
from .http_client import HttpClient, HttpResponse
from .models import BookProp, Player


class Sportsbook(ABC):
    name: str
    base_url: str

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self.http_client = http_client or HttpClient()

    def fetch_player_props(self, player: Player) -> list[BookProp]:
        """Fetch only this player's configured props, on demand."""
        url = self.player_url(player)
        response = self.http_client.get(url)
        return self.parse_player_props(response, player)

    def player_url(self, player: Player) -> str:
        # Replace this URL with the current public endpoint/page for the book.
        return f"{self.base_url}/player-props/{quote(player.id, safe='')}"

    @abstractmethod
    def parse_player_props(self, response: HttpResponse, player: Player) -> list[BookProp]:
        """Parse the current response schema; intentionally not guessed here."""
        raise NotImplementedError


class UnimplementedParserMixin:
    def parse_player_props(self, response: HttpResponse, player: Player) -> list[BookProp]:
        raise NotImplementedError(
            f"Implement the {self.name} parser for the current sportsbook layout/API response"
        )


class FanDuelSportsbook(UnimplementedParserMixin, Sportsbook):
    name = "fanduel"
    base_url = "https://sportsbook.fanduel.com"


class BetMGMSportsbook(UnimplementedParserMixin, Sportsbook):
    name = "betmgm"
    base_url = "https://sports.betmgm.com"


class DraftKingsSportsbook(UnimplementedParserMixin, Sportsbook):
    name = "draftkings"
    base_url = "https://sportsbook.draftkings.com"


class StaticSportsbook(Sportsbook):
    """Test/demo provider; useful until real parsers are supplied."""

    def __init__(self, name: str, props_by_player: dict[str, list[BookProp]]) -> None:
        self.name = name
        self.base_url = "https://example.invalid"
        self.props_by_player = props_by_player

    def fetch_player_props(self, player: Player) -> list[BookProp]:
        return [
            BookProp(
                player_id=prop.player_id,
                stat=prop.stat,
                line=prop.line,
                over_odds=prop.over_odds,
                under_odds=prop.under_odds,
                source=self.name,
            )
            for prop in self.props_by_player.get(player.id, [])
        ]

    def parse_player_props(self, response: HttpResponse, player: Player) -> list[BookProp]:
        raise NotImplementedError("StaticSportsbook does not parse HTTP responses")


def default_sportsbooks(http_client: HttpClient | None = None) -> dict[str, Sportsbook]:
    return {
        "fanduel": FanDuelSportsbook(http_client),
        "betmgm": BetMGMSportsbook(http_client),
        "draftkings": DraftKingsSportsbook(http_client),
    }


def validate_props(props: Iterable[BookProp], player: Player) -> list[BookProp]:
    allowed = set(STATS_BY_POSITION[player.position])
    valid: list[BookProp] = []
    for prop in props:
        if prop.player_id != player.id:
            continue
        if prop.stat in allowed:
            valid.append(prop)
    return valid
