"""Build pre-event features for every player-event (both tours combined history).
-> data/features.csv"""
import pandas as pd, numpy as np
def load_base():
    import os
    src = 'data/player_event.csv' if os.path.exists('data/player_event.csv') else 'data/results.csv'
    P = pd.read_csv(src, low_memory=False)
    E = pd.read_csv('data/events.csv')
    E = E[E.status == 'STATUS_FINAL'][['tour','event_id','name','start','course','par']]
    return P.merge(E, on=['tour','event_id'])

def build(P):
    """P = historical player-events (+ optional upcoming rows with no result). Returns features."""
    P = P.copy()
    P['start'] = pd.to_datetime(P.start.str[:10])
    P['n_field'] = P.groupby(['tour','event_id']).player_id.transform('size')
    P['fin'] = P.pos.where(P.pos.notna())
    P['pct'] = (P.fin / P.n_field)                       # finish percentile (lower = better)
    P['mc'] = ~P.made_cut.astype(bool)
    # 54-hole position (contention)
    P['t54'] = P[['r1','r2','r3']].sum(axis=1, min_count=3)
    P['pos54'] = P.groupby(['tour','event_id']).t54.rank(method='min')
    P['win'] = (P.fin == 1).astype(int); P['t5'] = (P.fin <= 5).astype(int); P['t20'] = (P.fin <= 20).astype(int)
    # same person across tours: ESPN ids differ by league? use normalised name as key
    P['key'] = P.player.str.lower().str.normalize('NFKD').str.encode('ascii','ignore').str.decode('ascii')
    P = P.sort_values(['key','start']).reset_index(drop=True)
    g = P.groupby('key')
    prev = lambda c, k=1: g[c].shift(k)
    P['days_since'] = (P.start - prev('start')).dt.days
    P['played_prev_wk'] = P.days_since.le(10)
    P['first_after_break'] = P.days_since.ge(28) | P.days_since.isna()
    # consecutive weeks played (chain of <=10 day gaps)
    chain = (~P.played_prev_wk).groupby(P.key).cumsum()
    P['consec'] = P.groupby([P.key, chain]).cumcount() + 1
    for k in (1, 2, 3):
        P[f'fin_l{k}'] = prev('fin', k); P[f'win_l{k}'] = prev('win', k); P[f't5_l{k}'] = prev('t5', k)
    P['won_last'] = P.win_l1.eq(1)
    P['won_last3'] = P[['win_l1','win_l2','win_l3']].eq(1).any(axis=1)
    P['runner_up_last'] = P.fin_l1.eq(2)
    P['t5_last'] = P.t5_l1.eq(1)
    P['mc_last'] = prev('mc').eq(True)
    roll = lambda c, n: g[c].transform(lambda s: s.shift(1).rolling(n, min_periods=n).sum())
    P['t5_in_l5'] = roll('t5', 5)
    P['mc_in_l5'] = g['mc'].transform(lambda s: s.astype(float).shift(1).rolling(5, min_periods=5).sum())
    P['contend_l3'] = g['pos54'].transform(lambda s: s.le(5).astype(float).shift(1).rolling(3, min_periods=1).max()).eq(1)
    P['pct_l5'] = g['pct'].transform(lambda s: s.shift(1).rolling(5, min_periods=3).mean())
    P['pct_l20'] = g['pct'].transform(lambda s: s.shift(1).rolling(20, min_periods=8).mean())
    P['form_up'] = P.pct_l5 < P.pct_l20 - 0.15            # recent form well above own baseline
    P['form_down'] = P.pct_l5 > P.pct_l20 + 0.15
    # course history (prior starts at same course)
    P = P.sort_values(['key','course','start'])
    gc = P.groupby(['key','course'])
    P['course_starts'] = gc.cumcount()
    P['course_pct'] = gc['pct'].transform(lambda s: s.shift(1).expanding().mean())
    P['course_t5_before'] = gc['t5'].transform(lambda s: s.shift(1).expanding().sum()).fillna(0)
    P['course_debut'] = P.course_starts.eq(0)
    P['course_good'] = P.course_pct.lt(0.25) & P.course_starts.ge(2)
    P = P.sort_values(['start','tour','event_id','fin'])
    return P.drop(columns=['key'])

if __name__ == '__main__':
    build(load_base()).to_csv('data/features.csv', index=False)

