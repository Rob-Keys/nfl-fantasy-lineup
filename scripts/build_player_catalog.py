#!/usr/bin/env python3
"""Build the frontend player catalog from nflverse's 2026 roster release."""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path
from urllib.request import urlopen


SOURCE_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "rosters/roster_2026.csv"
)
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "web" / "public" / "players.json"
FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
POSITION_ORDER = {
    position: index for index, position in enumerate(("QB", "RB", "WR", "TE", "K", "DEF"))
}

TEAM_NAMES = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "LV": "Las Vegas Raiders",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}


def load_roster() -> list[dict[str, str]]:
    with urlopen(SOURCE_URL, timeout=30) as response:
        text = io.TextIOWrapper(response, encoding="utf-8").read()
    return list(csv.DictReader(io.StringIO(text)))


def build_catalog(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    players = [
        {
            # gsis_id is nflverse's canonical player key and remains stable
            # across roster updates and the other IDs in the source row.
            "id": row["gsis_id"],
            "name": row["full_name"],
            "position": row["position"],
            "team": row["team"],
        }
        for row in rows
        if row["status"] == "ACT"
        and row["position"] in FANTASY_POSITIONS
        and row["gsis_id"]
        and row["full_name"]
        and row["team"]
    ]
    players.extend(
        {
            "id": f"def-{team}",
            "name": f"{name} Defense",
            "position": "DEF",
            "team": team,
        }
        for team, name in TEAM_NAMES.items()
    )
    return sorted(
        players,
        key=lambda player: (
            POSITION_ORDER[player["position"]],
            player["name"].casefold(),
            player["team"],
        ),
    )


def main() -> int:
    catalog = build_catalog(load_roster())
    OUTPUT_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(catalog)} players to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
