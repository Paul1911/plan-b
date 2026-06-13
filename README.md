# 1LIVE Plan B → Tidal playlist

Scrapes the songs played on WDR 1LIVE's *Plan B* show (Mon–Thu, 20:00–23:00 Berlin)
from [OnlineRadioBox](https://onlineradiobox.com/de/einslive/playlist/) and mirrors
the most recent show into a single Tidal playlist.

## How it works

1. Scrape the latest Plan B show from OnlineRadioBox (time-filtered to 20:00–23:00).
2. Fuzzy-match each song against the Tidal catalogue.
3. Replace the contents of one permanent Tidal playlist (its URL stays stable).

It runs automatically once a day via GitHub Actions (see *Deployment*).

## Local development & debugging

No credentials are needed to work on the scraper — this is the fast inner loop:

```sh
uv run python -m plan_b scrape                      # scrape & print the latest show
uv run python -m plan_b scrape --save-html ./debug_html   # capture pages to disk
uv run python -m plan_b scrape --from-html ./debug_html   # replay offline, no network
uv run pytest                                       # run the test suite
```

To exercise the matching / playlist code you need a Tidal session (see below):

```sh
uv run python -m plan_b run --dry-run               # scrape + match, write nothing
uv run python -m plan_b run                         # scrape + match + update playlist
```

`--save-html` / `--from-html` are the key debugging tools: capture a live page once,
then iterate on the parser against the saved copy with zero network calls. The saved
pages also make good test fixtures (see `tests/`).

## Tidal authentication

A one-time interactive login:

```sh
uv run python -m plan_b login
```

Open the printed URL, log in. This writes `.tidal_session.json`. The refresh token
inside does **not** rotate or expire, so this is genuinely a one-time step — every
later run (local or CI) refreshes the short-lived access token from it automatically.

## Deployment (GitHub Actions)

The workflow `.github/workflows/plan-b.yml` runs the pipeline on a schedule on
GitHub's runners (no server of your own required).

1. Log in locally: `uv run python -m plan_b login`.
2. Copy the **entire contents** of `.tidal_session.json`.
3. In the GitHub repo: **Settings → Secrets and variables → Actions → New repository
   secret**. Name it `TIDAL_SESSION_JSON`, paste the JSON.
4. Push this code. The job then runs **Tue–Fri at 06:00 UTC**, or on demand via
   **Actions → Update Plan B playlist → Run workflow** (with an optional dry-run).

## Configuration

All environment variables are optional:

| Variable | Default | Meaning |
|----------|---------|---------|
| `FUZZY_MATCH_THRESHOLD` | `75` | Minimum match score (0–100); higher is stricter |
| `TIMEZONE` | `Europe/Berlin` | Station timezone for the show window |
| `TIDAL_SESSION_JSON` | – | Session JSON for headless/CI use; overrides the file |
| `TIDAL_SESSION_FILE` | `.tidal_session.json` | Where the session is stored locally |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

## Spotify (optional, not enabled)

Spotify support exists (`--spotify`) but is off by default. It needs a Spotify
developer app; see `.env.example`.
