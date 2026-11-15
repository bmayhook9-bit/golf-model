"""Winner case studies: how each winner arrived (form, schedule, course, rating rank, model rank, market).
Model ranks use a model fitted on data BEFORE the event's year (no look-ahead).
python src/case_studies.py [year] [n]  -> reports/winner_case_studies.md"""
import sys, os, json
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import buildup_model as BM
year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
F = BM.load_training()
if 'bf_win' not in F: F['bf_win'] = np.nan
models = BM.fit(F[F.start.dt.year < year])
Y = F[F.start.dt.year == year].copy()
Y['pm_win'], Y['pm_t5'] = BM.predict(Y, models)
Y['model_rank'] = Y.groupby('ev').pm_win.rank(ascending=False, method='min')
Y['rating_rank'] = Y.groupby('ev').rating_f.rank(ascending=False, method='min')
Y['mkt_rank'] = Y.groupby('ev').bf_win.rank(method='min')
Y['field'] = Y.groupby('ev').player.transform('size')
# last 5 finishes, most recent first
H = pd.read_csv('data/features.csv', low_memory=False, parse_dates=['start'])
H = H[H.fin.notna() | H.mc.astype(bool)].sort_values('start')
H['key'] = BM.key(H.player)
def last5(k, d):
    h = H[(H.key == k) & (H.start < d)].tail(5)
    return ' / '.join('MC' if pd.isna(p) else str(int(p)) for p in h.fin[::-1])
W = Y[Y.win == 1].sort_values('start', ascending=False).head(n).copy()
W['key'] = BM.key(W.player)
W['last5'] = [last5(k, d) for k, d in zip(W.key, W.start)]
def tags(r):
    t = []
    if r.won_last3: t.append('won in last 3')
    if r.t5_in_l5 >= 2: t.append(f'{int(r.t5_in_l5)} top 5s in last 5')
    elif r.t5_last: t.append('top 5 last start')
    if r.contend_l3: t.append('contended in last 3')
    if r.played_prev_wk: t.append('played week before')
    if r.first_after_break: t.append('first start after break')
    if r.course_starts_c >= 2 and r.course_rel > 0.15: t.append('strong course history')
    if r.course_debut: t.append('course debut')
    if r.mc_in_l5 >= 2: t.append(f'{int(r.mc_in_l5)} MCs in last 5')
    return ', '.join(t)
W['build_up'] = [tags(r) for r in W.itertuples()]
cols = ['start','name','player','bf_win','mkt_rank','model_rank','rating_rank','field','last5','build_up']
W[cols].to_csv('data/case_studies.csv', index=False)
md = [f"# Winner case studies - {year}", "",
      "How each winner arrived. Ranks are within the field before the event; model = build-up model fitted on earlier years only.", "",
      "| Date | Event | Winner | Betfair close | Market rank | Model rank | Rating rank | Last 5 (recent first) | Build-up |",
      "|---|---|---|---|---|---|---|---|---|"]
for r in W.itertuples():
    f = lambda v: '-' if pd.isna(v) else str(int(v))
    md.append(f"| {r.start:%d %b} | {r.name} | {r.player} | {'-' if pd.isna(r.bf_win) else r.bf_win} | {f(r.mkt_rank)} | {f(r.model_rank)} | {f(r.rating_rank)} of {int(r.field)} | {r.last5} | {r.build_up} |")
# summary
s = W
md += ["", "**Summary**", "",
       f"- Winners: {len(s)} · in model top 10: {(s.model_rank <= 10).mean():.0%} · in market top 10: {(s[s.mkt_rank.notna()].mkt_rank <= 10).mean():.0%} (of {s.mkt_rank.notna().sum()} priced)",
       f"- Median rating rank: {s.rating_rank.median():.0f} · won in last 3: {s.won_last3.mean():.0%} · 2+ top 5s in last 5: {(s.t5_in_l5 >= 2).mean():.0%} · played week before: {s.played_prev_wk.mean():.0%}"]
os.makedirs('reports', exist_ok=True)
open('reports/winner_case_studies.md', 'w').write('\n'.join(md))
print('\n'.join(md[:20])); print('\n'.join(md[-3:]))
