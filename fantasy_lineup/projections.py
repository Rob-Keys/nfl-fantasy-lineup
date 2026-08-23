"""Fetching and averaging sportsbook props."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable

from .models import BookProp, Player, ProjectedStat, american_odds_probability
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
                    # A book contributes one main line per stat. Explicitly
                    # marked alternate props are ignored; the balance check
                    # handles feeds that return several unlabelled lines.
                    primary_by_source: dict[str, BookProp] = {}
                    for prop in props:
                        if prop.is_alternate:
                            continue
                        current = primary_by_source.get(prop.source)
                        if current is None or _is_more_primary(prop, current):
                            primary_by_source[prop.source] = prop
                    primary_props = list(primary_by_source.values())
                    if not primary_props:
                        continue
                    probabilities = [
                        probability
                        for probability in (prop.implied_over_probability for prop in primary_props)
                        if probability is not None
                    ]
                    stats[stat] = ProjectedStat(
                        stat=stat,
                        value=sum(prop.line for prop in primary_props) / len(primary_props),
                        sources=tuple(sorted({prop.source for prop in primary_props})),
                        market_over_probability=sum(probabilities) / len(probabilities) if probabilities else None,
                    )
            result.append(AggregatedPlayerProps(player=player, stats=stats))
        return result, sorted(warnings)


def _is_more_primary(candidate: BookProp, current: BookProp) -> bool:
    """Select the conventional main line when a feed leaves lines unlabelled."""
    candidate_complete = candidate.over_odds is not None and candidate.under_odds is not None
    current_complete = current.over_odds is not None and current.under_odds is not None
    if candidate_complete != current_complete:
        return candidate_complete
    if candidate_complete and current_complete:
        candidate_gap = abs(
            candidate.implied_over_probability
            - american_odds_probability(candidate.under_odds)
        )
        current_gap = abs(
            current.implied_over_probability
            - american_odds_probability(current.under_odds)
        )
        if candidate_gap != current_gap:
            return candidate_gap < current_gap
    return candidate.line < current.line
