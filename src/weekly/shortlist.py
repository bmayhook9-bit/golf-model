"""Weekly shortlist: ISN fair win prices vs Betfair, plus build-up flags and the tracked lead.
Inputs : latest inbox/isn/*.csv, latest data/live/prices_*.csv, data/results.csv + data/events.csv
Outputs: reports/shortlist_<date>.md (and prints it)"""
import sys, os, datetime as dt
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from common import norm, match_names, latest, stake_for
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json
from rapidfuzz import fuzz

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

_CACHE = {}
OUT = {'buildup': [], 'value': [], 'lead': [], 'targets': []}   # structured copies for the dashboard
def buildup_rank(event_name, players, tour):
    """Run the build-up model for an upcoming field. Returns DataFrame player, p_win, p_t5, why."""
    import features as FT, buildup_model as BM
    if 'base' not in _CACHE:
        _CACHE['base'] = FT.load_base(); _CACHE['cur'] = BM.current_ratings()
        _CACHE['models'] = json.load(open('models/buildup.json'))
    base = _CACHE['base']
    hist_names = base.player.dropna().unique()
    mp = match_names(players, hist_names)
    E = pd.read_csv('data/events.csv')
    nm = norm(str(event_name).replace('PGA ', '').replace('DPW Tour ', ''))
    sc = E.name.map(lambda n: fuzz.token_set_ratio(nm, norm(n)))
    course = E.loc[sc.idxmax(), 'course'] if len(sc) and sc.max() >= 70 else None
    up = pd.DataFrame({'player': [mp.get(p, p) for p in players], 'shown': players})
    up['tour'] = tour; up['event_id'] = 'upcoming'; up['name'] = event_name; up['course'] = course
    up['start'] = (pd.Timestamp.now(tz='UTC') + pd.Timedelta(days=3)).strftime('%Y-%m-%dT%H:%MZ')
    F = FT.build(pd.concat([base, up.drop(columns='shown')], ignore_index=True))
    F = F[F.event_id.astype(str) == 'upcoming'].copy()
    F['key'] = BM.key(F.player); F['rating'] = F.key.map(_CACHE['cur'])
    F = BM.prepare(F)
    F['p_win'], F['p_t5'] = BM.predict(F, _CACHE['models'])
    F['why'] = [BM.reasons(r, _CACHE['models']) for _, r in F.iterrows()]
    F['shown'] = F.player.map(dict(zip(up.player, up.shown)))
    return F.sort_values('p_win', ascending=False)[['shown', 'p_win', 'p_t5', 'why']]

def load_isn(fn):
    d = pd.read_csv(fn)
    d['isn_p'] = 100 / (d['Win Odds'] + 100)          # ISN gives American-style win odds
    d['isn_p'] = d.isn_p / d.isn_p.sum()               # fair book, sums to 1
    d['isn_price'] = 1 / d.isn_p
    return d[['Player', 'isn_p', 'isn_price', 'Model Rank']]

def buildup_lines(ev, players, tour, backs, flags, n=15):
    try:
        B = buildup_rank(ev, players, tour).head(n)
    except Exception as e:
        return [f"_Build-up ranking unavailable: {e}_", ""]
    out = [f"**Who's set up - build-up ranking: {ev}** (rating, form, schedule, course history. Ranks well, but does NOT beat the market on its own: compare its price with what's on offer)", "",
           "| # | Player | Model win % | Model price | Top 5 % | Betfair back | Last 3 | Why |", "|---|---|---|---|---|---|---|---|"]
    allB = buildup_rank(ev, players, tour)
    for i, r in enumerate(allB.itertuples(), 1):
        b = backs.get(r.shown)
        OUT['buildup'].append(dict(event=ev, tour=tour, rank=i, player=r.shown, model_win=r.p_win, model_top5=r.p_t5,
                                   betfair_back=b if b and b == b else None, last3=flags.get(norm(r.shown), {}).get('last3', ''), why=r.why))
    for i, r in enumerate(B.itertuples(), 1):
        b = backs.get(r.shown)
        out.append(f"| {i} | {r.shown} | {r.p_win:.1%} | {1 / r.p_win:.1f} | {r.p_t5:.0%} | {b if b and b == b else '-'} | {flags.get(norm(r.shown), {}).get('last3', '')} | {r.why} |")
    return out + [""]

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
    P['event'] = P.event.astype(str).str.strip()
    tour = P.event.str.match(r'^(PGA|DPW|DP World)') & ~P.event.str.contains('LPGA|Champions|Champs|Senior', case=False)
    pre = P.in_play.astype(str).str.lower() != 'true'
    win = P[(P.market_type == 'WINNER') & (P.status == 'ACTIVE') & tour & pre].copy()
    if win.empty:
        lines += ["No pre-tournament PGA Tour or DP World Tour win markets in this snapshot (markets usually open early in the week).", ""]
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
                OUT['value'].append(dict(event=ev, player=r.runner, back=r.back, isn_fair=r.isn_price, edge=r.edge,
                                         stake_to_win_500=stake_for('WINNER', r.back), last3=r.last3, flags=fl))
                lines.append(f"| {r.runner} | {r.back} | {r.isn_price:.1f} | {r.edge:+.0%} | £{stake_for('WINNER', r.back)} | {r.last3} | {fl} |")
            if v.empty: lines.append("| none | | | | | | |")
            lines.append("")
        # 2. the tracked lead (PGA, < 20.0, won in last 3)
        if is_pga:
            ld = g[(g.back < LEAD_MAX_PRICE) & g.won_last3]
            OUT['lead'] += [dict(event=ev, player=r.runner, back=r.back, last3=r.last3) for r in ld.itertuples()]
            lines += ["**Tracked lead** (PGA, back < 20.0, won in last 3 starts: 22 wins v 14.3 expected, 2023-26)", ""]
            lines += [f"- {r.runner} @ {r.back} (last 3: {r.last3})" for r in ld.itertuples()] or ["- none this week"]
            lines.append("")
        # 3. form watch: short-ish prices with recent contention
        fw = g[(g.back < 40) & g.contend_l3].sort_values('back')
        lines += ["**Form watch** (back < 40.0, top 5 after 54 holes in last 3) - priced in on history, for context", ""]
        lines += [f"- {r.runner} @ {r.back} (last 3: {r.last3})" for r in fw.itertuples()] or ["- none"]
        lines.append("")
        lines += buildup_lines(ev, list(g.runner), 'pga' if is_pga else 'eur', dict(zip(g.runner, g.back)), flags)
    if isn_fn and win.empty:
        # no Betfair markets yet: build-up ranking for the ISN field
        I0 = load_isn(isn_fn)
        lines += buildup_lines(os.path.basename(isn_fn).split('_', 1)[-1].replace('.csv', '').replace('-', ' '), list(I0.Player), 'pga', {}, flags)
    if isn_fn:
        I = load_isn(isn_fn).sort_values('isn_p', ascending=False).head(25)
        bf = {}
        if not win.empty:
            mp = match_names(I.Player, win.runner)
            bk = dict(zip(win.runner, win.back))
            bf = {p: bk.get(mp.get(p)) for p in I.Player}
        lines += [f"## Target prices - {os.path.basename(isn_fn)}", "",
                  f"Check bookmaker prices against these. Back only at or above the target (ISN fair price + {EDGE_MIN:.0%}).", "",
                  "| ISN rank | Player | ISN fair | Target (win) | Betfair back | Last 3 | Lead? |", "|---|---|---|---|---|---|---|"]
        for r in I.itertuples():
            f = flags.get(norm(r.Player), {})
            b = bf.get(r.Player)
            lead = 'yes' if f.get('won_last3') and (b or r.isn_price) < LEAD_MAX_PRICE else ''
            OUT['targets'].append(dict(isn_file=os.path.basename(isn_fn), isn_rank=int(r._4), player=r.Player, isn_fair=r.isn_price,
                                       target=r.isn_price * (1 + EDGE_MIN), betfair_back=b if b and b == b else None,
                                       last3=f.get('last3', ''), lead=lead))
            lines.append(f"| {int(r._4)} | {r.Player} | {r.isn_price:.1f} | {r.isn_price * (1 + EDGE_MIN):.1f} | {b if b and b == b else '-'} | {f.get('last3', '')} | {lead} |")
        lines.append("")
    if os.path.exists('data/case_studies.csv'):
        C = pd.read_csv('data/case_studies.csv', parse_dates=['start'])
        C = C[C.start >= pd.Timestamp.now() - pd.Timedelta(days=12)]
        if len(C):
            lines += ["## Last week's winners: how they arrived", "",
                      "| Event | Winner | Betfair close | Market rank | Model rank | Last 5 | Build-up |", "|---|---|---|---|---|---|---|"]
            f = lambda v: '-' if pd.isna(v) else str(int(v))
            lines += [f"| {r.name} | {r.player} | {'-' if pd.isna(r.bf_win) else r.bf_win} | {f(r.mkt_rank)} | {f(r.model_rank)} | {r.last5} | {r.build_up} |" for r in C.itertuples()]
            lines += ["", "Full season: `reports/winner_case_studies.md`", ""]
    lines += ["---", "Log any bet you place in `bets/log.csv` (date, event, player, market, price, stake, book). Closing prices and results fill in automatically."]
    md = '\n'.join(lines)
    os.makedirs('data/out', exist_ok=True)
    for k, rows in OUT.items():
        pd.DataFrame(rows).to_csv(f'data/out/{k}.csv', index=False)
    json.dump(dict(generated=dt.datetime.now(dt.timezone.utc).isoformat(), prices_file=os.path.basename(price_fn) if price_fn else None,
                   prices_age_h=round(float(age_h), 1) if price_fn else None, isn_file=os.path.basename(isn_fn) if isn_fn else None,
                   edge_min=EDGE_MIN, lead_max_price=LEAD_MAX_PRICE), open('data/out/meta.json', 'w'), indent=1)
    os.makedirs('reports', exist_ok=True)
    fn = f"reports/shortlist_{dt.date.today().isoformat()}.md"
    open(fn, 'w').write(md); open('reports/latest.md', 'w').write(md)
    print(md)
    return fn

if __name__ == '__main__':
    main(*sys.argv[1:])
