"""Small, serializable domain models used throughout the application."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class Player:
    id: str
    name: str
    position: str


@dataclass(frozen=True)
class BookProp:
    """A single book's prop line.

    A single line is a market threshold, not a statistically complete
    distribution. The default estimator therefore uses the line as a neutral
    expected-stat baseline and retains odds as market metadata.
    """

    player_id: str
    stat: str
    line: float
    over_odds: int | None = None
    under_odds: int | None = None
    source: str = "unknown"
    is_alternate: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.line, bool) or not isinstance(self.line, (int, float)) or not isfinite(float(self.line)):
            raise ValueError("Prop line must be a finite number")
        if self.line < 0:
            raise ValueError("Prop lines cannot be negative")
        for odds in (self.over_odds, self.under_odds):
            if odds is not None:
                american_odds_probability(odds)

    @property
    def implied_over_probability(self) -> float | None:
        if self.over_odds is None:
            return None
        return american_odds_probability(self.over_odds)


@dataclass(frozen=True)
class ProjectedStat:
    stat: str
    value: float
    sources: tuple[str, ...] = ()
    market_over_probability: float | None = None


@dataclass(frozen=True)
class PlayerProjection:
    player: Player
    stats: dict[str, ProjectedStat]
    fantasy_points: float


@dataclass(frozen=True)
class Lineup:
    slots: dict[str, tuple[PlayerProjection, ...]]
    total_points: float


@dataclass
class ProjectionResponse:
    lineup: Lineup
    projections: list[PlayerProjection]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineup": {
                "total_points": round(self.lineup.total_points, 4),
                "slots": {
                    slot: [serialize_projection(item) for item in players]
                    for slot, players in self.lineup.slots.items()
                },
            },
            "projections": [serialize_projection(item) for item in self.projections],
            "warnings": self.warnings,
        }


def american_odds_probability(odds: int) -> float:
    """Convert American odds to an unnormalized implied probability."""
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    if odds > 0:
        return 100 / (odds + 100)
    return -odds / (-odds + 100)


def serialize_projection(projection: PlayerProjection) -> dict[str, Any]:
    return {
        "player": {
            "id": projection.player.id,
            "name": projection.player.name,
            "position": projection.player.position,
        },
        "stats": {
            stat: {
                "value": round(item.value, 4),
                "sources": list(item.sources),
                **({"market_over_probability": round(item.market_over_probability, 4)}
                   if item.market_over_probability is not None else {}),
            }
            for stat, item in projection.stats.items()
        },
        "fantasy_points": round(projection.fantasy_points, 4),
    }
