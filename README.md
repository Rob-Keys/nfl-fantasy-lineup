# NFL fantasy lineup generator

## Frontend and Cloudflare proxy

The `web/` directory contains the lightweight TypeScript frontend. It calls
the same-origin `/api/lineup` Pages Function; it never receives the backend
URL's shared secret. The Pages Function forwards the request to the Lambda API
with `X-Internal-Api-Key`.

Deploy the Pages project with:

```text
Build command: npm --prefix web ci && npm --prefix web run build
Build output directory: web/dist
```

Configure these Cloudflare Pages Function variables:

- `BACKEND_API_URL`: the deployed API Gateway endpoint
- `ALLOWED_SITE_ORIGIN`: `https://nfl-fantasy-lineup.pages.dev` in production
- `BACKEND_SHARED_SECRET`: a secret stored with `wrangler pages secret put`

Configure the Lambda with the same `BACKEND_SHARED_SECRET` value. The Lambda
rejects direct requests that do not provide the matching internal header. This
is a server-to-server gate, not CORS; anyone can still call the public
Cloudflare route, so add user authentication later if the site itself must be
private.

### Cloudflare Pages setup

Connect the GitHub repository `Rob-Keys/nfl-fantasy-lineup` to a Cloudflare
Pages project, or create the project with Wrangler:

```bash
npx wrangler login
npx wrangler pages project create nfl-fantasy-lineup
npx wrangler pages secret put BACKEND_SHARED_SECRET --project-name nfl-fantasy-lineup
```

Set `BACKEND_API_URL` as a production Pages Function variable. Set
`BACKEND_SHARED_SECRET` as a production secret, then configure the same secret
in the Lambda environment. Generate it once and keep it out of Git:

```bash
openssl rand -base64 32
```

If using the GitHub integration, configure the Pages project with the build
command and output directory above. Functions are discovered from the root
`functions/` directory automatically. The browser calls `/api/lineup` on the
Pages origin, so no browser-side backend key or cross-origin API call is
needed. The Pages Function also rejects requests that do not look same-origin.
Apply rate limiting to the custom domain at the Cloudflare WAF layer; the
shared `pages.dev` hostname is not a zone owned by this account.

The player catalog in `web/public/players.json` is generated from nflverse's
2026 roster release. It currently includes active QB, RB, WR, TE, and K players
plus all 32 team defenses. Refresh it with:

```bash
python3 scripts/build_player_catalog.py
```

The generator uses the machine-readable
[`roster_2026.csv`](https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_2026.csv)
release and keeps nflverse's canonical `gsis_id` as each player ID. nflverse
publishes roster updates daily and documents the roster loader and release URL
in its [`nflreadr` documentation](https://github.com/nflverse/nflreadr/blob/main/R/load_rosters.R).

This is a small, standard-library-only Python implementation for an AWS Lambda behind API Gateway. It accepts a requested set of players, fetches only those players' props from the configured sportsbooks, averages matching lines, converts the result into fantasy points, and finds the highest-scoring legal lineup.

## Request shape

```json
{
  "players": [
    {"id": "josh-allen", "name": "Josh Allen", "position": "QB"},
    {"id": "rb-1", "name": "Example Runner", "position": "RB"}
  ],
  "sportsbooks": ["fanduel", "betmgm", "draftkings"],
  "scoring": "ppr",
  "lineup": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DEF": 1}
}
```

`scoring` can be `standard`, `half_ppr`, or `ppr` (PPR is the default), or a custom object such as `{"passing_yards": 0.05, "passing_tds": 6, "receptions": 1}`. `lineup` defaults to the standard single-QB roster and supports arbitrary counts such as `{"QB": 2, "RB": 2, "WR": 3, "TE": 1, "FLEX": 1}`.

## Important implementation note

A sportsbook over/under line is a threshold, not a full probability distribution. Odds alone cannot recover a mathematically exact expected stat value. This implementation uses each line as a neutral projected-stat estimate, averages the available books, and exposes the over implied probability as metadata. A later version can improve the estimator by adding alternate lines or a sport-specific distribution model without changing the lineup or scoring modules.

The FanDuel, BetMGM, and DraftKings adapters make the on-demand HTTP request but intentionally leave their response parsers as `NotImplementedError` stubs. Their public layouts/API schemas must be verified before production use. Do not bypass sportsbook terms of service, access controls, robots rules, or rate limits.

## Local test/demo

```bash
python -m unittest discover -s tests -v
```

The tests use `StaticSportsbook`, so they do not make network requests. Package `fantasy_lineup.handler.lambda_handler` as the Lambda handler.
