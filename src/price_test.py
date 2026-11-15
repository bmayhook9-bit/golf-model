"""Test each build-up flag against Betfair closing prices.
For flagged players: actual wins/top5s vs market-expected, and flat-stake ROI at closing price.
Split: 2023-25 (explore) vs 2026 (holdout)."""
import pandas as pd, numpy as np
F = pd.read_csv('data/features.csv', low_memory=False, parse_dates=['start'])
F = F[F.start.dt.year >= 2023]
FLAGS = ['won_last','won_last3','runner_up_last','t5_last','mc_last','contend_l3','played_prev_wk',
         'first_after_break','form_up','form_down','course_debut','course_good']
F['consec3p'] = F.consec >= 3; FLAGS.append('consec3p')
F['t5_2p_l5'] = F.t5_in_l5 >= 2; FLAGS.append('t5_2p_l5')
F['ALL'] = True
def prep(df, price, out, k):
    d = df[df[price].notna() & df.fin.notna() | df[price].notna() & df.mc.astype(bool)].copy()
    d['p'] = 1 / d[price]
    d['p'] = d.p * k / d.groupby(['tour','event_id']).p.transform('sum')   # strip margin
    # dead-heat: tied players share the places that fall inside the top k
    c = d.groupby(['tour','event_id','fin']).fin.transform('size')
    places = (np.minimum(k, d.fin + c - 1) - d.fin + 1).clip(lower=0)
    d['y'] = np.where(d.fin.notna(), places / c, 0.0)
    d['ret'] = d.y * d[price] - 1
    return d
rows = []
for mkt, price, out, k in [('win','bf_win','win',1), ('top5','bf_t5','t5',5)]:
    d = prep(F, price, out, k)
    for per, s in [('2023-25', d.start.dt.year <= 2025), ('2026', d.start.dt.year == 2026)]:
        for f in FLAGS + ['ALL']:
            x = d[s & d[f].astype(bool)]
            if len(x) < 30: continue
            a, e = x.y.sum(), x.p.sum()
            rows.append(dict(market=mkt, period=per, flag=f, n=len(x), actual=int(a), expected=round(e, 1),
                             ratio=round(a / e, 2), z=round((a - e) / np.sqrt(e), 1), roi=round(x.ret.mean(), 3)))
T = pd.DataFrame(rows)
T.to_csv('data/price_test.csv', index=False)
pv = T.pivot_table(index=['market','flag'], columns='period', values=['ratio','z','n','roi'])
pd.set_option('display.width', 200)
print(pv[[('n','2023-25'),('ratio','2023-25'),('z','2023-25'),('roi','2023-25'),('ratio','2026'),('z','2026'),('roi','2026')]].to_string())
