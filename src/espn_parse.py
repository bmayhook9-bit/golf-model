"""Parse raw ESPN scoreboards + meta into tidy CSVs:
data/events.csv, data/results.csv (player-event), data/holes.csv (hole scores where available)."""
import json, gzip, glob, os, csv
import pandas as pd
ev_rows, res, holes = [], [], []
for f in sorted(glob.glob('raw/espn/*.json.gz')):
    t, y, i = os.path.basename(f).split('.')[0].split('_')
    e = json.load(gzip.open(f)); c = (e.get('competitions') or [{}])[0]
    if not c.get('competitors'): continue
    st = (c.get('status') or {}).get('type', {}).get('name')
    mf = f'raw/meta/{t}_{i}.json'
    m = json.load(open(mf)) if os.path.exists(mf) else {}
    crs = (m.get('courses') or [{}])
    c0 = crs[0] if crs else {}
    ev_rows.append(dict(tour=t, event_id=i, name=e.get('name'), start=c.get('startDate') or e.get('date'),
        end=e.get('endDate'), status=st, n_players=len(c['competitors']), course=c0.get('name'),
        n_courses=len(crs), par=c0.get('shotsToPar'), yards=c0.get('totalYards'),
        city=(c0.get('address') or {}).get('city'), country=(c0.get('address') or {}).get('country'),
        purse=m.get('purse'), signature=m.get('isSignature')))
    for p in c['competitors']:
        if 'id' not in p or 'athlete' not in p: continue
        ls = p.get('linescores', [])
        rnds = [r for r in ls if r.get('period', 9) <= 4]
        row = dict(tour=t, event_id=i, player_id=p['id'], player=p['athlete'].get('displayName'),
                   order=p.get('order'), score=p.get('score'))
        nplayed = 0
        for r in rnds:
            k = r['period']; v = r.get('value') or None
            if v and v > 50: row[f'r{k}'] = v; nplayed += 1
            tt = [s for cat in (r.get('statistics') or {}).get('categories', []) for s in cat.get('stats', []) if 'teeTime' in str(s.get('name', '')) or 'PST' in str(s.get('displayValue', '')) or 'PDT' in str(s.get('displayValue',''))]
            if tt: row[f'tee{k}'] = tt[-1].get('displayValue')
            for h in r.get('linescores', []):
                if h.get('value'):
                    holes.append((t, i, p['id'], k, h['period'], h['value']))
        row['rounds'] = nplayed
        res.append(row)
os.makedirs('data', exist_ok=True)
E2 = pd.DataFrame(ev_rows); R = pd.DataFrame(res)
# finishing position with ties from order + total strokes; missed cut = fewer rounds than event max
R['total'] = R[[c for c in ['r1','r2','r3','r4'] if c in R]].sum(axis=1, min_count=1)
mx = R.groupby(['tour','event_id']).rounds.transform('max')
R['made_cut'] = R.rounds >= mx.clip(upper=4) - 0
R.loc[R.rounds < mx, 'made_cut'] = False
R['pos'] = None
fin = R[R.made_cut & (R.rounds == mx)].copy()
fin['pos'] = fin.groupby(['tour','event_id']).total.rank(method='min')
# winner = order 1 (handles play-offs, where totals tie)
fin.loc[fin.order == 1, 'pos'] = 1
fin.loc[(fin.order != 1) & (fin.pos == 1), 'pos'] = 2
R.loc[fin.index, 'pos'] = fin.pos
E2.to_csv('data/events.csv', index=False); R.to_csv('data/results.csv', index=False)
pd.DataFrame(holes, columns=['tour','event_id','player_id','round','hole','strokes']).to_csv('data/holes.csv', index=False)
print(len(E2), 'events', len(R), 'player-events', len(holes), 'hole scores')
