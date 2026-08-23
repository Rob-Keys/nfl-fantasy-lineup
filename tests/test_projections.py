import unittest

from fantasy_lineup.models import BookProp
from fantasy_lineup.projections import _is_more_primary


class ProjectionSelectionTests(unittest.TestCase):
    def test_one_sided_milestone_ladder_uses_threshold_near_even_probability(self):
        low_rung = BookProp("kyren", "rushing_yards", 19.5, over_odds=-2300, source="draftkings")
        balanced_rung = BookProp("kyren", "rushing_yards", 56.5, over_odds=-111, source="draftkings")

        self.assertTrue(_is_more_primary(balanced_rung, low_rung))
        self.assertFalse(_is_more_primary(low_rung, balanced_rung))


if __name__ == "__main__":
    unittest.main()
