"""Fantasy point calculation."""

from __future__ import annotations

from .models import Player, PlayerProjection, ProjectedStat


def _defense_points_allowed(value: float) -> float:
    """Apply the common tiered D/ST points-allowed scoring scale."""
    if value <= 0:
        return 10.0
    if value <= 6:
        return 7.0
    if value <= 13:
        return 4.0
    if value <= 20:
        return 1.0
    if value <= 27:
        return 0.0
    if value <= 34:
        return -1.0
    return -4.0


def score_player(player: Player, stats: dict[str, ProjectedStat], scoring: dict[str, float]) -> PlayerProjection:
    distance_stats = {"field_goals_0_39", "field_goals_40_49", "field_goals_50_plus"}
    has_distance_breakdown = bool(distance_stats.intersection(stats))
    points = 0.0
    for stat, item in stats.items():
        if stat == "field_goals_made" and has_distance_breakdown:
            continue
        if stat == "defense_points_allowed" and scoring.get("_defense_points_allowed_tiered", 0.0):
            points += _defense_points_allowed(item.value)
        else:
            points += item.value * scoring.get(stat, 0.0)
    return PlayerProjection(player=player, stats=stats, fantasy_points=points)
