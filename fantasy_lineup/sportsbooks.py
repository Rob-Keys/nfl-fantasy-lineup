"""Public sportsbook feeds and player-prop normalization.

The books do not expose one stable, documented schema to a browser. Their
public JSON feeds are nevertheless sufficient for this application when they
are treated as untrusted input: response shapes are checked, market names are
normalized, and only a requested player's supported statistics are emitted.

The adapters intentionally use the public sportsbook feeds only. They do not
attempt to bypass bot challenges, authentication, geofencing, or rate limits;
when a book declines a request the projection aggregator reports that book as
a warning and continues with the other books.
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator, Mapping
from typing import Any
from urllib.parse import quote, urlencode

from .config import STATS_BY_POSITION
from .http_client import HttpClient, HttpResponse, decode_json
from .models import BookProp, Player


_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _text(value: Any) -> str:
    """Turn the small localized/value wrappers used by the books into text."""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, Mapping):
        for key in ("value", "label", "name", "text", "display"):
            if key in value:
                result = _text(value[key])
                if result:
                    return result
    return ""


def _normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).lower()).strip()


def _walk(value: Any) -> Iterator[Mapping[str, Any]]:
    """Yield every mapping in an arbitrary JSON tree."""
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _first(value: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in value and value[key] not in (None, ""):
            return value[key]
    return None


def _american(value: Any) -> int | None:
    """Parse an American price from the variants used by public feeds."""
    if isinstance(value, Mapping):
        value = _first(value, ("americanOdds", "american", "americanDisplayOdds", "value", "display"))
    if isinstance(value, bool) or value is None:
        return None
    raw = str(value).strip().upper().replace("−", "-")
    if raw in {"EVEN", "EV"}:
        return 100
    match = re.fullmatch(r"([+-]?\d+)(?:\.0+)?", raw)
    if not match:
        return None
    odds = int(match.group(1))
    return odds or None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER_RE.search(str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def _price(node: Mapping[str, Any]) -> int | None:
    for key in (
        "americanOdds", "oddsAmerican", "american", "americanDisplayOdds",
        "displayOdds", "winRunnerOdds", "price", "odds",
    ):
        if key not in node:
            continue
        raw = node[key]
        if isinstance(raw, Mapping):
            raw = _first(raw, ("americanOdds", "american", "americanDisplayOdds", "display", "value"))
        result = _american(raw)
        if result is not None:
            return result
    return None


def _line(node: Mapping[str, Any], market_text: str) -> float | None:
    for key in ("points", "line", "handicap", "threshold", "total", "attr"):
        if key in node:
            raw = node[key]
            if isinstance(raw, Mapping):
                raw = _first(raw, ("value", "points", "line", "handicap"))
            result = _number(raw)
            if result is not None and result >= 0:
                return result

    # Some FanDuel yes-only markets encode their threshold in the title.
    match = re.search(r"(\d+)\s*\+", market_text)
    if match:
        return float(match.group(1)) - 0.5
    if re.search(r"\b(?:a|an|anytime)\b", market_text, re.IGNORECASE):
        return 0.5
    for phrase in ("over", "under"):
        match = re.search(rf"\b{phrase}\s*([0-9]+(?:\.[0-9]+)?)", market_text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _market_name(node: Mapping[str, Any]) -> str:
    value = _first(node, (
        "marketName", "market", "subcategoryName", "subcategory", "name", "label",
        "description", "offerName",
    ))
    return _text(value)


def _stat_for_market(market: str, position: str) -> str | None:
    """Map book-specific market labels to the application's stat vocabulary."""
    value = _normalize(market)
    # Combination markets cannot be represented by one BookProp.
    if any(token in value for token in ("same game", "combo", "parlay", "combined", "double")):
        return None

    rules = (
        (("passing yards", "pass yards", "pass yds"), "passing_yards"),
        (("passing touchdowns", "passing touchdown", "pass touchdowns", "pass tds"), "passing_tds"),
        (("interceptions thrown", "passing interceptions", "pass interceptions", "quarterback interceptions"), "interceptions"),
        (("rushing yards", "rush yards", "rush yds"), "rushing_yards"),
        (("rushing touchdowns", "rushing touchdown", "rush touchdowns", "rush tds"), "rushing_tds"),
        (("receiving yards", "reception yards", "receiving yds", "rec yards"), "receiving_yards"),
        (("receiving touchdowns", "receiving touchdown", "receiving tds", "rec touchdowns"), "receiving_tds"),
        (("receptions", "pass receptions", "total receptions"), "receptions"),
        (("fumbles lost", "lost fumbles"), "fumbles_lost"),
        (("field goals made", "field goal made", "made field goals"), "field_goals_made"),
        (("extra points made", "extra point made", "extra points"), "extra_points_made"),
        (("sacks", "defensive sacks", "team sacks"), "defense_sacks"),
        (("defensive interceptions", "defense interceptions", "team interceptions"), "defense_interceptions"),
        (("fumble recoveries", "defensive fumble recoveries", "team fumble recoveries"), "defense_fumble_recoveries"),
        (("defensive touchdowns", "defensive touchdown", "defense touchdowns", "defense tds"), "defense_tds"),
        (("points allowed", "team points allowed", "points conceded"), "defense_points_allowed"),
    )
    for needles, stat in rules:
        if any(needle in value for needle in needles):
            return stat

    if value in {"interceptions", "interception", "ints", "int"}:
        return "interceptions" if position == "QB" else "defense_interceptions" if position == "DEF" else None

    # Some pages use a generic touchdown market.
    if "touchdown" in value or re.search(r"\btds?\b", value):
        if position in {"WR", "TE"}:
            return "receiving_tds"
        if position in {"QB", "RB"}:
            return "rushing_tds"
    return None


def _contains_player(value: Any, player: Player) -> bool:
    target = _normalize(player.name)
    if not target:
        return False
    haystack = " ".join(_normalize(item) for node in _walk(value) for item in node.values())
    if target in haystack:
        return True
    # A few feeds use "last, first" while the catalog uses "first last".
    parts = target.split()
    return len(parts) >= 2 and f"{parts[-1]} {' '.join(parts[:-1])}" in haystack


def _selection_nodes(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    for key in ("runners", "outcomes", "selections", "options"):
        value = node.get(key)
        if isinstance(value, list):
            result.extend(item for item in value if isinstance(item, Mapping))
        elif isinstance(value, Mapping):
            result.extend(item for item in value.values() if isinstance(item, Mapping))
    return result or [node]


def _side(node: Mapping[str, Any]) -> str | None:
    value = _normalize(" ".join(_text(node.get(key)) for key in ("label", "name", "selection", "outcome", "totalsPrefix")))
    if re.search(r"\bover\b|\byes?\b", value):
        return "over"
    if re.search(r"\bunder\b|\bno\b", value):
        return "under"
    return None


def _props_from_market(market: Mapping[str, Any], player: Player, source: str) -> list[BookProp]:
    market_text = _market_name(market)
    stat = _stat_for_market(market_text, player.position)
    if stat is None or stat not in STATS_BY_POSITION[player.position]:
        return []

    selections = _selection_nodes(market)
    has_selection_player = any(_contains_player(selection, player) for selection in selections)
    market_matches = _contains_player(market, player)
    grouped: dict[float, dict[str, int | None]] = {}
    for selection in selections:
        if has_selection_player:
            if not _contains_player(selection, player):
                continue
        elif not market_matches:
            continue
        price = _price(selection)
        if price is None:
            continue
        selection_text = " ".join(_text(selection.get(key)) for key in ("label", "name", "selection", "outcome"))
        line = _line(selection, f"{market_text} {selection_text}")
        if line is None:
            line = _line(market, market_text)
        if line is None:
            continue
        bucket = grouped.setdefault(line, {"over": None, "under": None})
        side = _side(selection) or _side(market)
        bucket[side or "over"] = price

    return [
        BookProp(
            player_id=player.id,
            stat=stat,
            line=line,
            over_odds=values["over"],
            under_odds=values["under"],
            source=source,
        )
        for line, values in sorted(grouped.items())
        if values["over"] is not None or values["under"] is not None
    ]


def _parse_market_tree(value: Any, player: Player, source: str) -> list[BookProp]:
    props: list[BookProp] = []
    seen: set[tuple[str, float, int | None, int | None]] = set()
    for node in _walk(value):
        if not any(key in node for key in ("runners", "outcomes", "selections", "options")):
            continue
        for prop in _props_from_market(node, player, source):
            key = (prop.stat, prop.line, prop.over_odds, prop.under_odds)
            if key not in seen:
                seen.add(key)
                props.append(prop)
    return props


class Sportsbook(ABC):
    name: str
    base_url: str

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self.http_client = http_client or HttpClient()

    def fetch_player_props(self, player: Player) -> list[BookProp]:
        response = self.http_client.get(self.player_url(player))
        return self.parse_player_props(response, player)

    def player_url(self, player: Player) -> str:
        return f"{self.base_url}/player-props/{quote(player.id, safe='')}"

    @abstractmethod
    def parse_player_props(self, response: HttpResponse, player: Player) -> list[BookProp]:
        raise NotImplementedError


class FanDuelSportsbook(Sportsbook):
    """FanDuel's public content-managed and event-page feeds."""

    name = "fanduel"
    base_url = "https://sbapi.nj.sportsbook.fanduel.com"
    api_key = os.environ.get("FANDUEL_PUBLIC_API_KEY", "FhMFpcPWmeyZxOx")

    def player_url(self, player: Player) -> str:
        query = urlencode({"page": "CUSTOM", "customPageId": "nfl", "_ak": self.api_key})
        return f"{self.base_url}/api/content-managed-page?{query}"

    def _event_url(self, event_id: str) -> str:
        query = urlencode({"eventId": event_id, "tab": "popular", "_ak": self.api_key})
        return f"{self.base_url}/api/event-page?{query}"

    def fetch_player_props(self, player: Player) -> list[BookProp]:
        response = self.http_client.get(self.player_url(player))
        data = decode_json(response)
        props = _parse_market_tree(data, player, self.name)
        if props:
            return props

        # The content-managed page commonly contains only the event index;
        # player markets are then available on each event's public page.
        events = data.get("attachments", {}).get("events", {}) if isinstance(data, Mapping) else {}
        event_ids = list(events)[:32] if isinstance(events, Mapping) else []
        for event_id in event_ids:
            event_response = self.http_client.get(self._event_url(str(event_id)))
            props.extend(_parse_market_tree(decode_json(event_response), player, self.name))
        return _dedupe_props(props)

    def parse_player_props(self, response: HttpResponse, player: Player) -> list[BookProp]:
        return _parse_market_tree(decode_json(response), player, self.name)


class DraftKingsSportsbook(Sportsbook):
    """DraftKings event-group feed, with support for its normalized feed too."""

    name = "draftkings"
    base_url = "https://sportsbook-nash.draftkings.com"
    nfl_event_group = os.environ.get("DRAFTKINGS_NFL_EVENT_GROUP", "88808")
    site_code = os.environ.get("DRAFTKINGS_SITE_CODE", "dkusnj")

    def player_url(self, player: Player) -> str:
        return f"{self.base_url}/sites/US-SB/api/v5/eventgroups/{quote(self.nfl_event_group, safe='')}?format=json"

    def _sportscontent_league_url(self) -> str:
        return f"{self.base_url}/api/sportscontent/{self.site_code}/v1/leagues/{quote(self.nfl_event_group, safe='')}"

    def _sportscontent_subcategory_url(self, category_id: Any, subcategory_id: Any) -> str:
        return (
            f"{self.base_url}/api/sportscontent/{self.site_code}/v1/leagues/"
            f"{quote(self.nfl_event_group, safe='')}/categories/{quote(str(category_id), safe='')}"
            f"/subcategories/{quote(str(subcategory_id), safe='')}"
        )

    def parse_player_props(self, response: HttpResponse, player: Player) -> list[BookProp]:
        data = decode_json(response)
        props = _parse_market_tree(data, player, self.name)

        # The legacy event-group endpoint nests offers below a descriptor
        # whose name is the actual market (for example "Passing Yards").
        # Preserve that descriptor while parsing each offer's outcomes.
        for container in _walk(data):
            descriptors = container.get("offerSubcategoryDescriptors")
            if not isinstance(descriptors, list):
                continue
            for descriptor in descriptors:
                if not isinstance(descriptor, Mapping):
                    continue
                market_name = _text(_first(descriptor, ("name", "label", "subcategoryName")))
                subcategory = descriptor.get("offerSubcategory")
                offers = subcategory.get("offers") if isinstance(subcategory, Mapping) else descriptor.get("offers")
                if not isinstance(offers, list):
                    continue
                for group in offers:
                    entries = group if isinstance(group, list) else [group]
                    for offer in entries:
                        if not isinstance(offer, Mapping):
                            continue
                        outcomes = offer.get("outcomes")
                        if not isinstance(outcomes, (list, Mapping)):
                            continue
                        market = {"marketName": market_name, "outcomes": outcomes}
                        props.extend(_props_from_market(market, player, self.name))

        # Newer sportscontent responses split markets and selections into
        # sibling arrays instead of nesting outcomes under each offer.
        if isinstance(data, Mapping):
            markets = data.get("markets")
            selections = data.get("selections")
            if isinstance(markets, list) and isinstance(selections, list):
                by_market: dict[str, list[Mapping[str, Any]]] = {}
                for selection in selections:
                    if isinstance(selection, Mapping):
                        by_market.setdefault(str(selection.get("marketId")), []).append(selection)
                for market in markets:
                    if isinstance(market, Mapping):
                        container = dict(market)
                        container["outcomes"] = by_market.get(str(market.get("id")), [])
                        props.extend(_props_from_market(container, player, self.name))
        if props:
            return _dedupe_props(props)

        # DraftKings has been migrating NFL markets from the older eventgroup
        # endpoint to sportscontent. Discover only prop categories, then fetch
        # their subcategories so a request stays limited to the public NFL
        # offer rather than crawling unrelated sports.
        try:
            catalog_response = self.http_client.get(self._sportscontent_league_url())
            catalog = decode_json(catalog_response)
            categories = catalog.get("categories", []) if isinstance(catalog, Mapping) else []
            subcategories = catalog.get("subcategories", []) if isinstance(catalog, Mapping) else []
            prop_categories = {
                str(category.get("id"))
                for category in categories
                if isinstance(category, Mapping)
                and any(token in _normalize(category.get("name")) for token in ("prop", "player"))
            }
            subcategories_by_category: dict[str, list[Any]] = {}
            for subcategory in subcategories:
                if isinstance(subcategory, Mapping) and str(subcategory.get("categoryId")) in prop_categories:
                    subcategories_by_category.setdefault(str(subcategory.get("categoryId")), []).append(subcategory.get("id"))
            for category_id, subcategory_ids in subcategories_by_category.items():
                for subcategory_id in subcategory_ids:
                    sub_response = self.http_client.get(self._sportscontent_subcategory_url(category_id, subcategory_id))
                    props.extend(self.parse_player_props(sub_response, player))
        except Exception:
            # The legacy feed's failure should still be reported by the
            # aggregator; this fallback is best-effort because these IDs are
            # public presentation metadata and can change during the season.
            pass
        return _dedupe_props(props)


class BetMGMSportsbook(Sportsbook):
    """BetMGM/Entain public fixture feed and option-market schema."""

    name = "betmgm"
    base_url = "https://sports.nj.betmgm.com"
    access_id = os.environ.get(
        "BETMGM_PUBLIC_ACCESS_ID",
        "ZTllNjllODUtOWQwNS00YmU4LWE4NTEtZGZjOTkzMGM5OWU4",
    )

    def player_url(self, player: Player) -> str:
        params = {
            "x-bwin-accessid": self.access_id,
            "lang": "en-us",
            "country": "US",
            "userCountry": "US",
            "offerMapping": "Filtered",
            "sportIds": "11",
            "competitionIds": "35",
            "fixtureTypes": "Standard",
            "sortBy": "StartDate",
            "offerCategories": "Gridable",
        }
        return f"{self.base_url}/cds-api/bettingoffer/fixtures?{urlencode(params)}"

    def _official_api_url(self) -> str:
        return "https://sportsapi.nj.betmgm.com/offer/api/11/us/fixtures?language=en-us"

    def fetch_player_props(self, player: Player) -> list[BookProp]:
        # The first feed is the one used by the public BetMGM site. The
        # documented Sports API is a compatible fallback for other regions.
        response = self.http_client.get(self.player_url(player))
        props = self.parse_player_props(response, player)
        if props:
            return props
        try:
            fallback = self.http_client.get(self._official_api_url())
        except Exception:
            return props
        return _dedupe_props(props + self.parse_player_props(fallback, player))

    def parse_player_props(self, response: HttpResponse, player: Player) -> list[BookProp]:
        return _dedupe_props(_parse_market_tree(decode_json(response), player, self.name))


class StaticSportsbook(Sportsbook):
    """In-memory provider used by tests and local demos."""

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


def _dedupe_props(props: Iterable[BookProp]) -> list[BookProp]:
    result: list[BookProp] = []
    seen: set[tuple[str, str, float, int | None, int | None, str]] = set()
    for prop in props:
        key = (prop.player_id, prop.stat, prop.line, prop.over_odds, prop.under_odds, prop.source)
        if key not in seen:
            seen.add(key)
            result.append(prop)
    return result


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
