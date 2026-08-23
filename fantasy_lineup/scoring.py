"""Fantasy point calculation."""

from __future__ import annotations

from .models import Player, PlayerProjection, ProjectedStat


def score_player(player: Player, stats: dict[str, ProjectedStat], scoring: dict[str, float]) -> PlayerProjection:
    points = sum(item.value * scoring.get(stat, 0.0) for stat, item in stats.items())
    return PlayerProjection(player=player, stats=stats, fantasy_points=points)
