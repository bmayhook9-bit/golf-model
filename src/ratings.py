"""Simple pre-event player rating from field-relative round scores (both tours).
rating = exponentially weighted mean of strokes better than field average, prior rounds only.
-> data/ratings.csv (tour, event_id, player key, rating, n_rounds)"""
import pandas as pd, numpy as np
F = pd.read_csv('data/features.csv', low_memory=False, parse_dates=['start'])
F['key'] = F.player.str.lower().str.normalize('NFKD').str.encode('ascii','ignore').str.decode('ascii')
rows = []
for k in (1, 2, 3, 4):
    x = F[['tour','event_id','start','key',f'r{k}']].rename(columns={f'r{k}':'s'}).dropna()
    x['rnd'] = k
    rows.append(x)
R = pd.concat(rows)
R['rel'] = R.groupby(['tour','event_id','rnd']).s.transform('mean') - R.s   # + = better than field
R = R.sort_values(['key','start','rnd'])
HL = 40   # half-life in rounds
alpha = 1 - 0.5 ** (1 / HL)
R['ew'] = R.groupby('key').rel.transform(lambda s: s.shift(1).ewm(alpha=alpha, min_periods=12).mean())
R['n'] = R.groupby('key').cumcount()
# rating entering each event = value at its first round
pre = R.sort_values('rnd').groupby(['tour','event_id','key']).first()[['ew','n']].reset_index()
ev = R.groupby(['tour','event_id','key']).rel.mean().rename('event_rel').reset_index()
out = pre.merge(ev).rename(columns={'ew':'rating'})
out.to_csv('data/ratings.csv', index=False)
print(len(out), out.rating.notna().mean().round(2))
