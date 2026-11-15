"""Compact, committed copies of history for the dashboard (data/out/)."""
import os, pandas as pd, numpy as np
os.makedirs('data/out', exist_ok=True)
R = pd.read_csv('data/results.csv', low_memory=False); E = pd.read_csv('data/events.csv')
H = R.merge(E[['tour','event_id','name','start','course','status']], on=['tour','event_id'])
H = H[H.status == 'STATUS_FINAL']
H['date'] = H.start.str[:10]
H['finish'] = np.where(H.pos.notna(), H.pos.fillna(0).astype(int).astype(str), np.where(H.made_cut == False, 'MC', ''))
H[['date','tour','name','course','player','finish','pos','r1','r2','r3','r4','total']].sort_values('date').to_csv('data/out/player_history.csv', index=False)
if os.path.exists('data/ratings.csv'):
    import sys; sys.path.insert(0, 'src'); import buildup_model as BM
    BM.current_ratings().rename('rating').reset_index().to_csv('data/out/ratings_current.csv', index=False)
if os.path.exists('data/case_studies.csv'):
    pd.read_csv('data/case_studies.csv').to_csv('data/out/case_studies.csv', index=False)
pd.read_csv('data/course_profiles.csv').to_csv('data/out/course_profiles.csv', index=False) if os.path.exists('data/course_profiles.csv') else None
print('exported', len(H), 'history rows')
