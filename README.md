# golf-model

Personal golf betting research: build-up trends for winners and top finishers,
measured against Betfair prices, plus a weekly value shortlist.

## Status
- [x] Data spike: ESPN leaderboards (PGA hole-by-hole; DPWT rounds + tee times from ~2021)
- [x] Betfair BASIC historic golf (2023-2026): winner + top 5/10/20 closing prices
- [ ] Results/scorecard history, both tours
- [ ] Player-event table + build-up features
- [ ] Winner-profile report
- [ ] Weekly pipeline (GitHub Actions)

## Layout
- `src/betfair_extract.py` - Betfair BASIC files -> `data/betfair_prices.csv`
