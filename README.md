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

## Weekly routine
- **You:** drop the week's ISN CSV into `inbox/isn/` (GitHub web: Add file > Upload files) before Wed 17:00 UK.
- **Wed 17:00 UTC:** results refreshed, Betfair prices snapshot, shortlist posted as a GitHub issue (notification on your phone) and saved to `reports/latest.md`.
- **Wed 22:00 / Thu 05:00 / Thu 10:00 UTC:** extra price snapshots, so the last one before each event's start is its closing price.
- **You:** log any bet in `bets/log.csv` (date, event, player, market = win/top5/top10/top20, price, stake, book).
- **Mon 08:00 UTC:** results refreshed, bets graded (result, P/L, closing price, CLV), summary posted as an issue.

Secrets needed (Settings > Secrets and variables > Actions): `BF_USERNAME`, `BF_PASSWORD`, `BF_KEY` or `BF_APP_KEY` (Betfair delayed app key).

## Layout
- `src/betfair_extract.py` - Betfair BASIC files -> `data/betfair_prices.csv`
- `src/espn_fetch.py`, `src/espn_meta.py` - raw ESPN scoreboards + course metadata
- `src/espn_parse.py` - -> `data/events.csv`, `data/results.csv`, `data/holes.csv`
- `src/link_prices.py` - -> `data/player_event.csv` (results + closing prices)
