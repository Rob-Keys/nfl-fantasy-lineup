import unittest

from fantasy_lineup.config import lineup_from_config, scoring_from_config


class ConfigTests(unittest.TestCase):
    def test_ppr_and_custom_scoring(self):
        self.assertEqual(scoring_from_config("ppr")["receptions"], 1)
        self.assertEqual(scoring_from_config("half_ppr")["receptions"], 0.5)
        self.assertEqual(scoring_from_config({"receptions": 2})["receptions"], 2.0)

    def test_invalid_lineup_is_rejected(self):
        with self.assertRaises(ValueError):
            lineup_from_config({"QB": -1})


if __name__ == "__main__":
    unittest.main()
