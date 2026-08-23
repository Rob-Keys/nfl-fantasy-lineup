"""Fetching and averaging sportsbook props."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable

from .models import BookProp, Player, ProjectedStat
from .sportsbooks import Sportsbook, validate_props


@dataclass(frozen=True)
class AggregatedPlayerProps:
    player: Player
    stats: dict[str, ProjectedStat]


class ProjectionAggregator:
    def __init__(self, sportsbooks: dict[str, Sportsbook], max_workers: int = 6) -> None:
        self.sportsbooks = sportsbooks
        self.max_workers = max(1, max_workers)

    def collect(self, players: Iterable[Player], sportsbook_names: Iterable[str]) -> tuple[list[AggregatedPlayerProps], list[str]]:
        players = list(players)
        names = list(dict.fromkeys(sportsbook_names))
        unknown = [name for name in names if name not in self.sportsbooks]
        if unknown:
            raise ValueError(f"Unknown sportsbooks: {', '.join(unknown)}")
        if not names:
            raise ValueError("At least one sportsbook is required")

        warnings: list[str] = []
        props_by_player_stat: dict[str, dict[str, list[BookProp]]] = defaultdict(lambda: defaultdict(list))

        # Requests are independent and remain on-demand: one task per
        # requested player/book pair, with no global player cache.
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(players) * len(names))) as pool:
            futures = {
                pool.submit(self.sportsbooks[book].fetch_player_props, player): (player, book)
                for player in players
                for book in names
            }
            for future in as_completed(futures):
                player, book = futures[future]
                try:
                    raw_props = future.result()
                    for prop in validate_props(raw_props, player):
                        props_by_player_stat[player.id][prop.stat].append(prop)
                except NotImplementedError as exc:
                    warnings.append(f"{book} parser unavailable for {player.name}: {exc}")
                except Exception as exc:  # one provider should not erase other books
                    warnings.append(f"{book} failed for {player.name}: {exc}")

        result: list[AggregatedPlayerProps] = []
        for player in players:
            stats: dict[str, ProjectedStat] = {}
            for stat, props in props_by_player_stat[player.id].items():
                if props:
                    probabilities = [
                        probability
                        for probability in (prop.implied_over_probability for prop in props)
                        if probability is not None
                    ]
                    stats[stat] = ProjectedStat(
                        stat=stat,
                        value=sum(prop.line for prop in props) / len(props),
                        sources=tuple(sorted({prop.source for prop in props})),
                        market_over_probability=sum(probabilities) / len(probabilities) if probabilities else None,
                    )
            result.append(AggregatedPlayerProps(player=player, stats=stats))
        return result, sorted(warnings)
