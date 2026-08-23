import unittest

from fantasy_lineup.models import BookProp
from fantasy_lineup.projections import _is_more_primary, odds_adjusted_value


class ProjectionSelectionTests(unittest.TestCase):
    def test_one_sided_milestone_ladder_uses_threshold_near_even_probability(self):
        low_rung = BookProp("kyren", "rushing_yards", 19.5, over_odds=-2300, source="draftkings")
        balanced_rung = BookProp("kyren", "rushing_yards", 56.5, over_odds=-111, source="draftkings")

        self.assertTrue(_is_more_primary(balanced_rung, low_rung))
        self.assertFalse(_is_more_primary(low_rung, balanced_rung))

    def test_occurrence_market_uses_fair_probability_instead_of_half(self):
        prop = BookProp(
            "def", "defense_tds", 0.5, over_odds=-200, under_odds=150,
        )

        # Raw implied probabilities are 2/3 and 0.4; after removing vig the
        # over probability is (2/3) / ((2/3) + 0.4) = 0.625.
        self.assertAlmostEqual(odds_adjusted_value(prop), 0.625)

    def test_kyren_rushing_yards_price_moves_the_posted_line(self):
        prop = BookProp("kyren", "rushing_yards", 57.5, over_odds=-200, under_odds=150)

        self.assertAlmostEqual(odds_adjusted_value(prop), 64.6875)

    def test_missing_odds_keep_line_only_fallback(self):
        self.assertEqual(odds_adjusted_value(BookProp("kyren", "rushing_yards", 57.5)), 57.5)


if __name__ == "__main__":
    unittest.main()
