"""Data-driven comparable courses: courses are similar when the same players over/under-perform
their rating at both. Course sims are learned on 2021-24 only; the fit feature is tested on 2025-26.
-> data/course_sims.csv, data/comp_fit.csv"""
import pandas as pd, numpy as np
F = pd.read_csv('data/features.csv', low_memory=False, parse_dates=['start'])
F['key'] = F.player.str.lower().str.normalize('NFKD').str.encode('ascii','ignore').str.decode('ascii')
Rt = pd.read_csv('data/ratings.csv')
F = F.merge(Rt[['tour','event_id','key','rating','event_rel']], on=['tour','event_id','key'], how='left')
F = F[(F.start.dt.year >= 2021) & F.rating.notna() & F.event_rel.notna() & F.course.notna()]
F['resid'] = F.event_rel - F.rating          # + = played better than rating
F['ck'] = F.tour + '|' + F.course
# player x course mean residual, training window
T = F[F.start.dt.year <= 2024]
M = T.groupby(['key','ck']).resid.mean().unstack()
courses = [c for c in M.columns if M[c].notna().sum() >= 60]
sims = []
for i, a in enumerate(courses):
    for b in courses[i+1:]:
        both = M[[a, b]].dropna()
        n = len(both)
        if n < 25: continue
        r = both[a].corr(both[b])
        sims.append((a, b, n, r * n / (n + 60)))          # shrink toward 0 for small overlaps
S = pd.DataFrame(sims, columns=['a','b','n','sim'])
S = pd.concat([S, S.rename(columns={'a':'b','b':'a'})])
S.to_csv('data/course_sims.csv', index=False)
print('course pairs', len(S)//2, 'sim quantiles', S.sim.quantile([.5,.9,.99]).round(3).tolist())
# comp fit for each player-event: weighted mean of the player's PRIOR residuals at similar courses (sim>0)
F = F.sort_values('start')
simd = {(a, b): s for a, b, s in zip(S.a, S.b, S.sim) if s > 0.05}
hist = {}
cf, cw = [], []
for k, ck, res in zip(F.key, F.ck, F.resid):
    h = hist.setdefault(k, [])
    num = den = 0.0
    for c2, r2 in h:
        w = 1.0 if c2 == ck else simd.get((ck, c2), 0)
        if w: num += w * r2; den += w
    cf.append(num / den if den else np.nan); cw.append(den)
    h.append((ck, res))
F['comp_fit'] = cf; F['comp_w'] = cw
F[['tour','event_id','key','comp_fit','comp_w']].to_csv('data/comp_fit.csv', index=False)
# 1) does comp_fit predict residual (beyond rating) out of sample?
O = F[(F.start.dt.year >= 2025) & (F.comp_w >= 2)]
print('2025-26: corr(comp_fit, residual) =', round(O.comp_fit.corr(O.resid), 3), 'n =', len(O))
# 2) against the price
for mkt, price, out, k in [('win','bf_win','win',1), ('top5','bf_t5','t5',5)]:
    d = F[F[price].notna() & (F.start.dt.year >= 2023)].copy()
    d['p'] = 1 / d[price]; d['p'] = d.p * k / d.groupby(['tour','event_id']).p.transform('sum')
    c = d.groupby(['tour','event_id','fin']).fin.transform('size')
    d['y'] = np.where(d.fin.notna(), (np.minimum(k, d.fin + c - 1) - d.fin + 1).clip(lower=0) / c, 0.0)
    d['ret'] = d.y * d[price] - 1
    q = d[d.comp_w >= 2]
    q['band'] = pd.qcut(q.comp_fit, 5, labels=['worst fit','2','3','4','best fit'])
    for per, s in [('2023-24', q.start.dt.year <= 2024), ('2025-26', q.start.dt.year >= 2025)]:
        g = q[s].groupby('band', observed=True).agg(n=('y','size'), actual=('y','sum'), expected=('p','sum'), roi=('ret','mean'))
        g['ratio'] = (g.actual / g.expected).round(2); g['z'] = ((g.actual - g.expected) / np.sqrt(g.expected)).round(1)
        print(f'\n{mkt} {per} by comp-course fit quintile'); print(g.round(2).to_string())
