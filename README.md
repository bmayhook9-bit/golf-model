# golf-model

Personal golf betting research: build-up trends for winners and top finishers,
measured against Betfair prices, plus a weekly value shortlist.

## Status
- [x] Data spike: ESPN leaderboards (PGA hole-by-hole; DPWT rounds + tee times from ~2021)
- [x] Betfair BASIC historic golf (2023-2026): winner + top 5/10/20 closing prices
- [x] Results/scorecard history, both tours (ESPN, 2019-26; DPWT rounds from 2021, PGA hole-by-hole ~365 events)
- [x] Betfair prices linked to events/players (~300 events 2023-26, 288/304 winners priced)
- [x] Player-event table + results/schedule/contention/course-history features (`src/features.py`)
- [x] First price test of build-up flags (`src/price_test.py`): none beat Betfair close 2023-25
- [x] Simple player ratings (`src/ratings.py`) and course profiles incl. slope (`src/course_profile.py`)
- [x] Segment tests (`src/segment_test.py`): lead = in-form PGA favourites (<20.0) underpriced
- [ ] Winner-profile report
- [x] Weekly pipeline (GitHub Actions) - built, dry-run tested; live Betfair calls untested until key is added

- [x] Build-up model (`src/buildup_model.py`, `models/buildup.json`): field-strength-adjusted rating + form + course. Ranks well (winner in top 10 31%) but below Betfair close on 2026 holdout; shown as 'who's set up', not a betting signal

- [x] Comparable-course fit from results (`src/course_fit.py`): no predictive value (corr 0.05), no price edge - dropped
- [x] Winner case studies (`src/case_studies.py` -> `reports/winner_case_studies.md`), refreshed weekly; last week's winners shown in the shortlist

## Dashboard
Main dashboard: **Golf Betting Desk** (Claude artifact https://claude.ai/artifact/2UFGAfcTtH18PwpTJrkpRP), built from `app/dashboard.html` by `src/build_html.py` -> `dist/dashboard.html` (rebuilt by the weekly jobs).
Workflow: review who's set up -> type bookmaker prices -> add value bets to the betting card (target-profit staking) -> copy lines into `bets/log.csv`.

Older Streamlit version: `app/dashboard.py` (Streamlit): This week (who's set up vs market, value, lead), Target prices (type a bookmaker price to check it),
Players, Winners, Bets (P/L, CLV), Research. Reads `data/out/`, `bets/`, refreshed by the weekly jobs.
Deploy: share.streamlit.io > Create app > repo `bmayhook9-bit/golf-model`, branch `main`, file `app/dashboard.py`.

## Weekly routine
- **You:** drop the week's ISN CSV into `inbox/isn/` (GitHub web: Add file > Upload files) before Mon 12:00 UK (or Tue 12:00 at the latest).
- **Mon 11:30, Tue 11:30, Wed 17:00, 22:00, Thu 05:00, 10:00 UTC (your Mac):** Betfair price snapshots (`betfair-prices` workflow, self-hosted runner - Betfair blocks GitHub's US servers). The last one before each event's start is its closing price.
- **Mon 12:00 + Tue 12:00 UTC (GitHub):** results refreshed, shortlist with value picks and ISN target prices posted as a GitHub issue and saved to `reports/latest.md`. Warns if prices are stale.
- **You:** log any bet in `bets/log.csv` (date, event, player, market = win/top5/top10/top20, price, stake, book).
- **Mon 08:00 UTC:** results refreshed, last week's bets graded (result, P/L, closing price, CLV), summary posted as an issue.

Secrets needed (Settings > Secrets and variables > Actions): `BF_USERNAME`, `BF_PASSWORD`, `BF_KEY` or `BF_APP_KEY` (Betfair delayed app key).

## Layout
- `src/betfair_extract.py` - Betfair BASIC files -> `data/betfair_prices.csv`
- `src/espn_fetch.py`, `src/espn_meta.py` - raw ESPN scoreboards + course metadata
- `src/espn_parse.py` - -> `data/events.csv`, `data/results.csv`, `data/holes.csv`
- `src/link_prices.py` - -> `data/player_event.csv` (results + closing prices)
