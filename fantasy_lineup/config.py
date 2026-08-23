"""Explicit application defaults and configuration validation."""

from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any

# These are intentionally explicit. They are a reasonable PPR starting point,
# not a claim that every fantasy platform uses the same rules.
SCORING_PRESETS: dict[str, dict[str, float]] = {
    "standard": {
        "passing_yards": 0.04,
        "passing_tds": 4,
        "interceptions": -2,
        "rushing_yards": 0.1,
        "rushing_tds": 6,
        "receptions": 0,
        "receiving_yards": 0.1,
        "receiving_tds": 6,
        "fumbles_lost": -2,
        "field_goals_made": 3,
        "extra_points_made": 1,
        "defense_sacks": 1,
        "defense_interceptions": 2,
        "defense_fumble_recoveries": 2,
        "defense_tds": 6,
        "defense_points_allowed": 0,
    },
    "half_ppr": {
        "passing_yards": 0.04,
        "passing_tds": 4,
        "interceptions": -2,
        "rushing_yards": 0.1,
        "rushing_tds": 6,
        "receptions": 0.5,
        "receiving_yards": 0.1,
        "receiving_tds": 6,
        "fumbles_lost": -2,
        "field_goals_made": 3,
        "extra_points_made": 1,
        "defense_sacks": 1,
        "defense_interceptions": 2,
        "defense_fumble_recoveries": 2,
        "defense_tds": 6,
        "defense_points_allowed": 0,
    },
    "ppr": {
        "passing_yards": 0.04,
        "passing_tds": 4,
        "interceptions": -2,
        "rushing_yards": 0.1,
        "rushing_tds": 6,
        "receptions": 1,
        "receiving_yards": 0.1,
        "receiving_tds": 6,
        "fumbles_lost": -2,
        "field_goals_made": 3,
        "extra_points_made": 1,
        "defense_sacks": 1,
        "defense_interceptions": 2,
        "defense_fumble_recoveries": 2,
        "defense_tds": 6,
        "defense_points_allowed": 0,
    },
}

DEFAULT_LINEUP: dict[str, int] = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "K": 1,
    "DEF": 1,
}

# These are the stat keys the adapters should attempt to return by position.
# Missing props are allowed; their contribution is zero rather than guessed.
STATS_BY_POSITION: dict[str, tuple[str, ...]] = {
    "QB": (
        "passing_yards", "passing_tds", "interceptions",
        "rushing_yards", "rushing_tds", "fumbles_lost",
    ),
    "RB": (
        "rushing_yards", "rushing_tds", "receptions",
        "receiving_yards", "receiving_tds", "fumbles_lost",
    ),
    "WR": (
        "receptions", "receiving_yards", "receiving_tds", "fumbles_lost",
    ),
    "TE": (
        "receptions", "receiving_yards", "receiving_tds", "fumbles_lost",
    ),
    "K": ("field_goals_made", "extra_points_made"),
    "DEF": (
        "defense_sacks", "defense_interceptions",
        "defense_fumble_recoveries", "defense_tds", "defense_points_allowed",
    ),
}

VALID_POSITIONS = frozenset(STATS_BY_POSITION)
FLEX_POSITIONS = frozenset({"RB", "WR", "TE"})


def scoring_from_config(value: Any) -> dict[str, float]:
    """Resolve a preset name or validate a custom stat-to-points mapping."""
    if value is None:
        return deepcopy(SCORING_PRESETS["ppr"])
    if isinstance(value, str):
        try:
            return deepcopy(SCORING_PRESETS[value.lower()])
        except KeyError as exc:
            raise ValueError(f"Unknown scoring preset: {value}") from exc
    if not isinstance(value, dict) or not value:
        raise ValueError("scoring must be a preset name or non-empty object")
    result: dict[str, float] = {}
    for stat, points in value.items():
        if not isinstance(stat, str) or not stat:
            raise ValueError("Custom scoring stat names must be non-empty strings")
        if isinstance(points, bool) or not isinstance(points, (int, float)) or not isfinite(float(points)):
            raise ValueError(f"Scoring value for {stat} must be numeric")
        result[stat] = float(points)
    return result


def lineup_from_config(value: Any) -> dict[str, int]:
    """Resolve and validate a lineup slot-to-count mapping."""
    if value is None:
        return deepcopy(DEFAULT_LINEUP)
    if not isinstance(value, dict) or not value:
        raise ValueError("lineup must be a non-empty object")
    result: dict[str, int] = {}
    for slot, count in value.items():
        normalized = str(slot).upper()
        if normalized not in VALID_POSITIONS and normalized != "FLEX":
            raise ValueError(f"Unknown lineup slot: {slot}")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"Lineup count for {slot} must be a non-negative integer")
        if count:
            result[normalized] = count
    if not result:
        raise ValueError("lineup must contain at least one positive slot count")
    return result
