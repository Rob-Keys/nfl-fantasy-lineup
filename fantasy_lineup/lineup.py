"""Optimal assignment of projected players to roster slots."""

from __future__ import annotations

from functools import lru_cache

from .config import FLEX_POSITIONS
from .models import Lineup, PlayerProjection


def slot_eligible(slot: str, position: str) -> bool:
    return position in FLEX_POSITIONS if slot == "FLEX" else position == slot


def optimize_lineup(projections: list[PlayerProjection], slot_counts: dict[str, int]) -> Lineup:
    """Return the maximum-point legal lineup, without reusing a player.

    A memoized search is preferable to independently selecting each slot: it
    correctly handles competition between flex and dedicated positions.
    """
    slot_instances = [slot for slot, count in slot_counts.items() for _ in range(count)]
    slot_instances.sort(key=lambda slot: sum(slot_eligible(slot, item.player.position) for item in projections))
    candidate_indices = tuple(
        tuple(index for index, item in enumerate(projections) if slot_eligible(slot, item.player.position))
        for slot in slot_instances
    )

    @lru_cache(maxsize=None)
    def solve(slot_index: int, used_mask: int) -> tuple[float, tuple[int, ...]] | None:
        if slot_index == len(slot_instances):
            return 0.0, ()
        best: tuple[float, tuple[int, ...]] | None = None
        for index in candidate_indices[slot_index]:
            if used_mask & (1 << index):
                continue
            remainder = solve(slot_index + 1, used_mask | (1 << index))
            if remainder is None:
                continue
            score = projections[index].fantasy_points + remainder[0]
            candidate = (score, (index,) + remainder[1])
            if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1] < best[1]):
                best = candidate
        return best

    solved = solve(0, 0)
    if solved is None:
        missing = [slot for slot, indices in zip(slot_instances, candidate_indices) if not indices]
        raise ValueError(f"Insufficient eligible players for lineup slots: {', '.join(sorted(set(missing)))}")

    assigned: dict[str, list[PlayerProjection]] = {slot: [] for slot in slot_counts}
    for slot, index in zip(slot_instances, solved[1]):
        assigned[slot].append(projections[index])
    return Lineup(
        slots={slot: tuple(items) for slot, items in assigned.items()},
        total_points=solved[0],
    )
