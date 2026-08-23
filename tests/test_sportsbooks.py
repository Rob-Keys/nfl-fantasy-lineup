import json
import unittest

from fantasy_lineup.http_client import HttpResponse
from fantasy_lineup.models import Player
from fantasy_lineup.sportsbooks import (
    BetMGMSportsbook,
    DraftKingsSportsbook,
    FanDuelSportsbook,
)


def response(payload):
    return HttpResponse(200, json.dumps(payload).encode("utf-8"), {"Content-Type": "application/json"})


class SportsbookParserTests(unittest.TestCase):
    player = Player("gsis-josh-allen", "Josh Allen", "QB")

    def test_fanduel_runner_markets_pair_over_and_under(self):
        payload = {
            "attachments": {
                "markets": {
                    "market-1": {
                        "marketName": "Passing Yards",
                        "runners": [
                            {
                                "runnerName": "Josh Allen",
                                "label": "Over",
                                "handicap": 250.5,
                                "isPlayerSelection": True,
                                "winRunnerOdds": {"americanDisplayOdds": {"americanOdds": "+105"}},
                            },
                            {
                                "runnerName": "Josh Allen",
                                "label": "Under",
                                "handicap": 250.5,
                                "isPlayerSelection": True,
                                "winRunnerOdds": {"americanDisplayOdds": {"americanOdds": "-125"}},
                            },
                        ],
                    }
                }
            }
        }

        props = FanDuelSportsbook().parse_player_props(response(payload), self.player)

        self.assertEqual(len(props), 1)
        self.assertEqual(props[0].stat, "passing_yards")
        self.assertEqual(props[0].line, 250.5)
        self.assertEqual(props[0].over_odds, 105)
        self.assertEqual(props[0].under_odds, -125)
        self.assertEqual(props[0].player_id, self.player.id)

    def test_draftkings_legacy_event_group_descriptor_is_used(self):
        payload = {
            "eventGroup": {
                "offerCategories": [
                    {
                        "name": "Passing Props",
                        "offerSubcategoryDescriptors": [
                            {
                                "name": "Passing Yards",
                                "offerSubcategory": {
                                    "offers": [[
                                        {
                                            "outcomes": [
                                                {
                                                    "participant": "Josh Allen",
                                                    "label": "Over 250.5",
                                                    "points": 250.5,
                                                    "oddsAmerican": "+100",
                                                },
                                                {
                                                    "participant": "Josh Allen",
                                                    "label": "Under 250.5",
                                                    "points": 250.5,
                                                    "oddsAmerican": "-120",
                                                },
                                            ]
                                        }
                                    ]]
                                },
                            }
                        ],
                    }
                ]
            }
        }

        props = DraftKingsSportsbook().parse_player_props(response(payload), self.player)

        self.assertEqual(len(props), 1)
        self.assertEqual(props[0].stat, "passing_yards")
        self.assertEqual(props[0].over_odds, 100)
        self.assertEqual(props[0].under_odds, -120)

    def test_betmgm_option_market_handles_localized_values(self):
        payload = {
            "fixtures": [
                {
                    "optionMarkets": [
                        {
                            "status": "Visible",
                            "name": {"value": "Passing Touchdowns"},
                            "options": [
                                {
                                    "name": {"value": "Josh Allen Over"},
                                    "attr": "1.5",
                                    "price": {"americanOdds": "-110"},
                                },
                                {
                                    "name": {"value": "Josh Allen Under"},
                                    "attr": "1.5",
                                    "price": {"americanOdds": "+105"},
                                },
                            ],
                        }
                    ]
                }
            ]
        }

        props = BetMGMSportsbook().parse_player_props(response(payload), self.player)

        self.assertEqual(len(props), 1)
        self.assertEqual(props[0].stat, "passing_tds")
        self.assertEqual(props[0].line, 1.5)
        self.assertEqual(props[0].over_odds, -110)
        self.assertEqual(props[0].under_odds, 105)

    def test_draftkings_normalized_market_and_selection_arrays_are_joined(self):
        payload = {
            "markets": [{"id": "market-1", "name": "Passing Yards"}],
            "selections": [
                {
                    "marketId": "market-1",
                    "label": "Over 250.5",
                    "points": 250.5,
                    "participants": [{"name": "Josh Allen"}],
                    "displayOdds": {"american": "−110"},
                },
                {
                    "marketId": "market-1",
                    "label": "Under 250.5",
                    "points": 250.5,
                    "participants": [{"name": "Josh Allen"}],
                    "displayOdds": {"american": "+100"},
                },
            ],
        }

        props = DraftKingsSportsbook().parse_player_props(response(payload), self.player)

        self.assertEqual(len(props), 1)
        self.assertEqual(props[0].line, 250.5)
        self.assertEqual(props[0].over_odds, -110)
        self.assertEqual(props[0].under_odds, 100)

    def test_threshold_market_is_converted_to_half_integer_line(self):
        payload = {
            "marketName": "To Record 2+ Rushing Yards",
            "runners": [
                {
                    "runnerName": "Josh Allen",
                    "isPlayerSelection": True,
                    "winRunnerOdds": {"americanDisplayOdds": {"americanOdds": "-115"}},
                }
            ],
        }

        props = FanDuelSportsbook().parse_player_props(response(payload), self.player)

        self.assertEqual(len(props), 1)
        self.assertEqual(props[0].stat, "rushing_yards")
        self.assertEqual(props[0].line, 1.5)
        self.assertEqual(props[0].over_odds, -115)


if __name__ == "__main__":
    unittest.main()
