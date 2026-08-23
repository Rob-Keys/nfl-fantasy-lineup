import unittest

from fantasy_lineup.config import scoring_from_config
from fantasy_lineup.models import Player, ProjectedStat
from fantasy_lineup.scoring import score_player


class ScoringTests(unittest.TestCase):
    def test_kicker_distance_breakdown_does_not_double_count_total(self):
        player = Player("k", "Kicker", "K")
        stats = {
            "field_goals_made": ProjectedStat("field_goals_made", 3),
            "field_goals_0_39": ProjectedStat("field_goals_0_39", 1),
            "field_goals_40_49": ProjectedStat("field_goals_40_49", 1),
            "field_goals_50_plus": ProjectedStat("field_goals_50_plus", 1),
        }

        projection = score_player(player, stats, scoring_from_config("ppr"))

        self.assertEqual(projection.fantasy_points, 12)

    def test_defense_uses_points_allowed_tiers(self):
        player = Player("def", "Defense", "DEF")
        stats = {"defense_points_allowed": ProjectedStat("defense_points_allowed", 24)}

        projection = score_player(player, stats, scoring_from_config("ppr"))

        self.assertEqual(projection.fantasy_points, 0)


if __name__ == "__main__":
    unittest.main()
