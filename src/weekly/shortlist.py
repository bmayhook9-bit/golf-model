"""Weekly shortlist: ISN fair win prices vs Betfair, plus build-up flags and the tracked lead.
Inputs : latest inbox/isn/*.csv, latest data/live/prices_*.csv, data/results.csv + data/events.csv
Outputs: reports/shortlist_<date>.md (and prints it)"""
import sys, os, datetime as dt
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from common import norm, match_names, latest, stake_for

EDGE_MIN = 0.20          # ISN probability x Betfair price - 1
MAX_PRICE = 200.0        # ignore deep long shots: thin markets, noisy prices
LEAD_MAX_PRICE = 20.0

def history_flags():
    R = pd.read_csv('data/results.csv', low_memory=False)
    E = pd.read_csv('data/events.csv')
    E = E[E.status == 'STATUS_FINAL'][['tour', 'event_id', 'start', 'name']]
    R = R.merge(E, on=['tour', 'event_id']).sort_values('start')
    R['key'] = R.player.map(norm)
    R['t54'] = R[['r1', 'r2', 'r3']].sum(axis=1, min_count=3)
    R['pos54'] = R.groupby(['tour', 'event_id']).t54.rank(method='min')
    out = {}
    for k, g in R.groupby('key'):
        last = g.tail(3)
        out[k] = dict(won_last3=bool((last.pos == 1).any()), t5_last=bool(g.pos.iloc[-1] <= 5) if pd.notna(g.pos.iloc[-1]) else False,
                      runner_up_last=bool(g.pos.iloc[-1] == 2), contend_l3=bool((last.pos54 <= 5).any()),
                      last3=' / '.join('MC' if pd.isna(p) else f'{int(p)}' for p in last.pos[::-1]))
    return out

def load_isn(fn):
    d = pd.read_csv(fn)
    d['isn_p'] = 100 / (d['Win Odds'] + 100)          # ISN gives American-style win odds
    d['isn_p'] = d.isn_p / d.isn_p.sum()               # fair book, sums to 1
    d['isn_price'] = 1 / d.isn_p
    return d[['Player', 'isn_p', 'isn_price', 'Model Rank']]

def main(isn_fn=None, price_fn=None):
    isn_fn = isn_fn or latest('inbox/isn/*.csv'); price_fn = price_fn or latest('data/live/prices_*.csv')
    flags = history_flags()
    lines = [f"# Golf shortlist - {dt.date.today().isoformat()}", ""]
    if not price_fn:
        lines += ["**No Betfair price snapshot yet** - check the Mac runner (Actions > betfair-prices)."]
        md = '\n'.join(lines); os.makedirs('reports', exist_ok=True); open('reports/latest.md', 'w').write(md); print(md); return
    P = pd.read_csv(price_fn)
    age_h = (pd.Timestamp.now(tz='UTC') - pd.to_datetime(P.snapshot.iloc[0], utc=True)).total_seconds() / 3600
    lines += [f"Prices: `{os.path.basename(price_fn)}` ({age_h:.0f}h old) · ISN model: `{os.path.basename(isn_fn) if isn_fn else 'none'}`", ""]
    if age_h > 12:
        lines += [f"**Warning: prices are {age_h:.0f} hours old** - the Mac snapshot probably didn't run. Check prices before betting.", ""]
    win = P[(P.market_type == 'WINNER') & (P.status == 'ACTIVE')].copy()
    for ev, g in win.groupby('event'):
        g = g.copy()
        g['fl'] = g.runner.map(lambda n: flags.get(norm(n), {}))
        g['won_last3'] = g['fl'].map(lambda f: f.get('won_last3', False))
        g['contend_l3'] = g['fl'].map(lambda f: f.get('contend_l3', False))
        g['t5_last'] = g['fl'].map(lambda f: f.get('t5_last', False))
        g['last3'] = g['fl'].map(lambda f: f.get('last3', ''))
        is_pga = str(ev).startswith('PGA') or 'PGA' in str(ev)
        lines += [f"## {ev}", ""]
        # 1. value vs ISN (PGA only, ISN covers PGA)
        if isn_fn and is_pga:
            I = load_isn(isn_fn)
            mp = match_names(I.Player, g.runner)
            I['runner'] = I.Player.map(mp)
            v = g.merge(I.dropna(subset=['runner']), on='runner', how='inner')
            v['edge'] = v.isn_p * v.back - 1
            v = v[(v.edge >= EDGE_MIN) & v.back.notna() & (v.back <= MAX_PRICE)].sort_values('edge', ascending=False).head(12)
            lines += [f"**Value vs ISN** (edge >= {EDGE_MIN:.0%}; matched {len(mp)}/{len(I)} ISN players)", "",
                      "| Player | Back | ISN fair | Edge | Stake to win £500 | Last 3 | Flags |", "|---|---|---|---|---|---|---|"]
            for r in v.itertuples():
                fl = ', '.join(k for k in ('won_last3', 'contend_l3', 't5_last') if getattr(r, k))
                lines.append(f"| {r.runner} | {r.back} | {r.isn_price:.1f} | {r.edge:+.0%} | £{stake_for('WINNER', r.back)} | {r.last3} | {fl} |")
            if v.empty: lines.append("| none | | | | | | |")
            lines.append("")
        # 2. the tracked lead (PGA, < 20.0, won in last 3)
        if is_pga:
            ld = g[(g.back < LEAD_MAX_PRICE) & g.won_last3]
            lines += ["**Tracked lead** (PGA, back < 20.0, won in last 3 starts: 22 wins v 14.3 expected, 2023-26)", ""]
            lines += [f"- {r.runner} @ {r.back} (last 3: {r.last3})" for r in ld.itertuples()] or ["- none this week"]
            lines.append("")
        # 3. form watch: short-ish prices with recent contention
        fw = g[(g.back < 40) & g.contend_l3].sort_values('back')
        lines += ["**Form watch** (back < 40.0, top 5 after 54 holes in last 3) - priced in on history, for context", ""]
        lines += [f"- {r.runner} @ {r.back} (last 3: {r.last3})" for r in fw.itertuples()] or ["- none"]
        lines.append("")
    lines += ["---", "Log any bet you place in `bets/log.csv` (date, event, player, market, price, stake, book). Closing prices and results fill in automatically."]
    md = '\n'.join(lines)
    os.makedirs('reports', exist_ok=True)
    fn = f"reports/shortlist_{dt.date.today().isoformat()}.md"
    open(fn, 'w').write(md); open('reports/latest.md', 'w').write(md)
    print(md)
    return fn

if __name__ == '__main__':
    main(*sys.argv[1:])
