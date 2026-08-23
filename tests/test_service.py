import unittest

from fantasy_lineup.models import BookProp
from fantasy_lineup.service import FantasyLineupService
from fantasy_lineup.sportsbooks import StaticSportsbook


class ServiceTests(unittest.TestCase):
    def test_end_to_end_averages_books_scores_and_assigns_lineup(self):
        players = [
            {"id": "qb", "name": "Quarterback", "position": "QB"},
            {"id": "rb", "name": "Runner", "position": "RB"},
        ]
        books = {
            "book-a": StaticSportsbook("book-a", {"qb": [BookProp("qb", "passing_yards", 300, over_odds=-110)]}),
            "book-b": StaticSportsbook("book-b", {"qb": [BookProp("qb", "passing_yards", 280, over_odds=110)]}),
        }
        response = FantasyLineupService(books).generate({
            "players": players,
            "sportsbooks": ["book-a", "book-b"],
            "scoring": {"passing_yards": 0.05},
            "lineup": {"QB": 1},
        })
        self.assertEqual(response.projections[0].stats["passing_yards"].value, 290)
        self.assertAlmostEqual(
            response.projections[0].stats["passing_yards"].market_over_probability,
            (100 / 210 + 110 / 210) / 2,
        )
        self.assertEqual(response.projections[0].fantasy_points, 14.5)
        self.assertEqual(response.lineup.slots["QB"][0].player.id, "qb")

    def test_only_one_primary_line_per_book_is_averaged(self):
        players = [{"id": "qb", "name": "Quarterback", "position": "QB"}]
        books = {
            "book-a": StaticSportsbook("book-a", {"qb": [
                BookProp("qb", "passing_yards", 300, over_odds=-110, under_odds=-110),
                BookProp("qb", "passing_yards", 350, over_odds=200, under_odds=-300),
            ]}),
            "book-b": StaticSportsbook("book-b", {
                "qb": [BookProp("qb", "passing_yards", 280, over_odds=-110, under_odds=-110)],
            }),
        }
        response = FantasyLineupService(books).generate({
            "players": players,
            "sportsbooks": ["book-a", "book-b"],
            "scoring": {"passing_yards": 0.05},
            "lineup": {"QB": 1},
        })

        self.assertEqual(response.projections[0].stats["passing_yards"].value, 290)

    def test_player_without_props_can_fill_a_slot_at_zero_points(self):
        players = [
            {"id": "qb", "name": "Quarterback", "position": "QB"},
            {"id": "rb", "name": "Runner", "position": "RB"},
        ]
        books = {
            "book-a": StaticSportsbook("book-a", {
                "qb": [BookProp("qb", "passing_yards", 300)],
            }),
        }

        response = FantasyLineupService(books).generate({
            "players": players,
            "sportsbooks": ["book-a"],
            "scoring": {"passing_yards": 0.05},
            "lineup": {"QB": 1},
        })

        self.assertEqual(response.lineup.slots["QB"][0].player.id, "qb")
        self.assertEqual(response.lineup.total_points, 15.0)
        self.assertTrue(any("Runner" in warning for warning in response.warnings))

    def test_missing_position_props_do_not_make_a_legal_roster_impossible(self):
        players = [
            {"id": "qb", "name": "Quarterback", "position": "QB"},
            {"id": "k", "name": "Kicker", "position": "K"},
        ]
        books = {
            "book-a": StaticSportsbook("book-a", {
                "qb": [BookProp("qb", "passing_yards", 300)],
            }),
        }

        response = FantasyLineupService(books).generate({
            "players": players,
            "sportsbooks": ["book-a"],
            "scoring": {"passing_yards": 0.05},
            "lineup": {"QB": 1, "K": 1},
        })

        self.assertEqual(response.lineup.slots["K"][0].player.id, "k")
        self.assertEqual(response.lineup.slots["K"][0].fantasy_points, 0)
        self.assertTrue(any("Kicker" in warning for warning in response.warnings))


if __name__ == "__main__":
    unittest.main()
