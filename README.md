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
- [ ] Winner-profile report
- [ ] Weekly pipeline (GitHub Actions)

## Layout
- `src/betfair_extract.py` - Betfair BASIC files -> `data/betfair_prices.csv`
- `src/espn_fetch.py`, `src/espn_meta.py` - raw ESPN scoreboards + course metadata
- `src/espn_parse.py` - -> `data/events.csv`, `data/results.csv`, `data/holes.csv`
- `src/link_prices.py` - -> `data/player_event.csv` (results + closing prices)
