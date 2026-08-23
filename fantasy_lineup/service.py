"""Application orchestration independent of the AWS Lambda adapter."""

from __future__ import annotations

from typing import Any

from .config import VALID_POSITIONS, lineup_from_config, scoring_from_config
from .lineup import optimize_lineup
from .models import Player, ProjectionResponse
from .projections import ProjectionAggregator
from .scoring import score_player
from .sportsbooks import Sportsbook, default_sportsbooks


class FantasyLineupService:
    def __init__(self, sportsbooks: dict[str, Sportsbook] | None = None) -> None:
        self.sportsbooks = sportsbooks or default_sportsbooks()
        self.aggregator = ProjectionAggregator(self.sportsbooks)

    def generate(self, request: dict[str, Any]) -> ProjectionResponse:
        players = parse_players(request.get("players"))
        scoring = scoring_from_config(request.get("scoring", "ppr"))
        lineup = lineup_from_config(request.get("lineup"))
        sportsbook_names = request.get("sportsbooks", list(self.sportsbooks))
        if not isinstance(sportsbook_names, list) or not all(isinstance(name, str) for name in sportsbook_names):
            raise ValueError("sportsbooks must be an array of names")

        aggregated, warnings = self.aggregator.collect(players, sportsbook_names)
        projections = [score_player(item.player, item.stats, scoring) for item in aggregated]
        if not any(item.stats for item in aggregated):
            raise ValueError("No supported props were returned by the requested sportsbooks")
        optimized = optimize_lineup(projections, lineup)
        return ProjectionResponse(lineup=optimized, projections=projections, warnings=warnings)


def parse_players(value: Any) -> list[Player]:
    if not isinstance(value, list) or not value:
        raise ValueError("players must be a non-empty array")
    result: list[Player] = []
    ids: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("Each player must be an object")
        raw_id = raw.get("id")
        raw_name = raw.get("name")
        if raw_id is None or raw_name is None:
            raise ValueError("Each player requires id, name, and a valid position")
        player_id = str(raw_id).strip()
        name = str(raw_name).strip()
        position = str(raw.get("position", "")).upper().strip()
        if not player_id or not name or position not in VALID_POSITIONS:
            raise ValueError("Each player requires id, name, and a valid position")
        if player_id in ids:
            raise ValueError(f"Duplicate player id: {player_id}")
        ids.add(player_id)
        result.append(Player(id=player_id, name=name, position=position))
    return result
