"""(A) Do favourites beat the price at high-slope courses? (slope from other editions only)
(B) Build-up flags by segment: tour x price band. Market = Betfair close, margin stripped, dead-heat adjusted."""
import pandas as pd, numpy as np
F = pd.read_csv('data/features.csv', low_memory=False, parse_dates=['start'])
F['key'] = F.player.str.lower().str.normalize('NFKD').str.encode('ascii','ignore').str.decode('ascii')
Rt = pd.read_csv('data/ratings.csv'); F = F.merge(Rt, on=['tour','event_id','key'], how='left')
# leave-one-edition-out course slope
D = F[F.start.dt.year >= 2021].copy()
D['top60'] = D.groupby(['tour','event_id']).rating.rank(ascending=False) <= 60
G = D[D.rating.notna() & D.top60].copy()
G['x'] = G.rating - G.groupby(['tour','event_id']).rating.transform('mean')
G['y'] = G.event_rel - G.groupby(['tour','event_id']).event_rel.transform('mean')
slope = {}
for (t, c), g in G.groupby(['tour','course']):
    eids = g.event_id.unique()
    if len(eids) < 3: continue
    for e in eids:
        o = g[g.event_id != e]; slope[(t, e)] = np.polyfit(o.x, o.y, 1)[0]
F['slope'] = [slope.get((t, e)) for t, e in zip(F.tour, F.event_id)]
F = F[F.start.dt.year >= 2023]
def prep(price, k):
    d = F[F[price].notna() & (F.fin.notna() | F.mc.astype(bool))].copy()
    d['p'] = 1 / d[price]; d['p'] = d.p * k / d.groupby(['tour','event_id']).p.transform('sum')
    c = d.groupby(['tour','event_id','fin']).fin.transform('size')
    d['y'] = np.where(d.fin.notna(), (np.minimum(k, d.fin + c - 1) - d.fin + 1).clip(lower=0) / c, 0.0)
    d['ret'] = d.y * d[price] - 1
    d['mrank'] = d.groupby(['tour','event_id']).p.rank(ascending=False)
    return d
def summ(x):
    a, e = x.y.sum(), x.p.sum()
    return pd.Series(dict(n=len(x), actual=round(a, 1), expected=round(e, 1), ratio=round(a / e, 2),
                          z=round((a - e) / np.sqrt(e), 1), roi=round(x.ret.mean(), 3)))
pd.set_option('display.width', 200)
for mkt, price, k in [('WIN', 'bf_win', 1), ('TOP5', 'bf_t5', 5)]:
    d = prep(price, k)
    s = d[d.slope.notna()].copy()
    s['slope_band'] = pd.qcut(s.slope.rank(method='first'), 3, labels=['low', 'mid', 'high'])
    s['market_band'] = np.where(s.mrank <= 10, 'top10 in market', 'rest')
    print(f'\n== {mkt}: favourites vs rest by course slope (events with slope: {s.event_id.nunique()})')
    print(s.groupby(['slope_band', 'market_band'], observed=True).apply(summ, include_groups=False).to_string())
    d['band'] = pd.cut(d[price], [1, 20, 80, 1e9] if k == 1 else [1, 5, 15, 1e9], labels=['short', 'mid', 'long'])
    print(f'\n== {mkt}: by tour x price band (all players)')
    print(d.groupby(['tour', 'band'], observed=True).apply(summ, include_groups=False).to_string())
    for f in ['won_last3', 'runner_up_last', 't5_last', 'contend_l3', 'form_up']:
        x = d[d[f].astype(bool)]
        print(f'\n-- {mkt} flag {f} by tour x band'); print(x.groupby(['tour', 'band'], observed=True).apply(summ, include_groups=False).to_string())
