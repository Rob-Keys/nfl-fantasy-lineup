import unittest

from fantasy_lineup.lineup import optimize_lineup
from fantasy_lineup.models import Player, PlayerProjection


def projection(player_id, position, points):
    return PlayerProjection(Player(player_id, player_id, position), {}, points)


class LineupTests(unittest.TestCase):
    def test_flex_competes_with_dedicated_slots_without_reuse(self):
        projections = [
            projection("rb-high", "RB", 20),
            projection("rb-mid", "RB", 15),
            projection("wr-high", "WR", 19),
            projection("te", "TE", 10),
        ]
        lineup = optimize_lineup(projections, {"RB": 1, "WR": 1, "FLEX": 1})
        chosen = {item.player.id for items in lineup.slots.values() for item in items}
        self.assertEqual(chosen, {"rb-high", "wr-high", "rb-mid"})
        self.assertEqual(lineup.total_points, 54)

    def test_insufficient_players_is_clear(self):
        with self.assertRaisesRegex(ValueError, "QB"):
            optimize_lineup([projection("rb", "RB", 10)], {"QB": 1})


if __name__ == "__main__":
    unittest.main()
