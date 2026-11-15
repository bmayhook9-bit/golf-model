"""Build-up model: P(win) and P(top 5) from rating, form, schedule and course history.
Logistic regression on pre-event features, probabilities normalised within each event (sum 1 / 5).
python src/buildup_model.py           -> evaluate on 2026 holdout vs Betfair, then fit on all and save models/buildup.json
"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'weekly'))

FEATS = ['rating_rel', 'no_rating', 'won_last3', 'runner_up_last', 't5_last', 't5_in_l5', 'contend_l3',
         'mc_in_l5', 'form_delta', 'played_prev_wk', 'first_after_break', 'course_rel', 'course_starts_c', 'course_debut']
LABELS = {'won_last3': 'won in last 3', 'runner_up_last': 'runner-up last start', 't5_last': 'top 5 last start',
          't5_in_l5': 'top 5s in last 5', 'contend_l3': 'contended in last 3', 'form_delta': 'form trending up',
          'course_rel': 'good course history', 'rating_rel': 'class (rating)'}

def key(s):
    return s.str.lower().str.normalize('NFKD').str.encode('ascii', 'ignore').str.decode('ascii')

def current_ratings(hl=40):
    """Latest rating per player using ALL rounds to date (for upcoming events)."""
    R = pd.read_csv('data/results.csv', low_memory=False); E = pd.read_csv('data/events.csv')
    R = R.merge(E[['tour', 'event_id', 'start']], on=['tour', 'event_id'])
    rows = []
    for k in (1, 2, 3, 4):
        x = R[['tour', 'event_id', 'start', 'player', f'r{k}']].rename(columns={f'r{k}': 's'}).dropna(); x['rnd'] = k; rows.append(x)
    X = pd.concat(rows); X['rel'] = X.groupby(['tour', 'event_id', 'rnd']).s.transform('mean') - X.s
    X['key'] = key(X.player); X = X.sort_values(['key', 'start', 'rnd'])
    a = 1 - 0.5 ** (1 / hl)
    X['raw'] = X.rel
    for _ in range(2):   # same field-strength adjustment as ratings.py
        X['ew'] = X.groupby('key').rel.transform(lambda s: s.shift(1).ewm(alpha=a, min_periods=12).mean())
        fs = X.groupby(['tour', 'event_id']).ew.transform('mean')
        X['rel'] = X.raw + (fs - fs.mean()).fillna(0)
    out = X.groupby('key').rel.apply(lambda s: s.ewm(alpha=a, min_periods=12).mean().iloc[-1])
    return out.dropna()

def prepare(F):
    F = F.copy()
    F['ev'] = F.tour.astype(str) + '_' + F.event_id.astype(str)
    F['no_rating'] = F.rating.isna().astype(int)
    lo = F.groupby('ev').rating.transform(lambda s: s.quantile(0.1))
    F['rating_f'] = F.rating.fillna(lo).fillna(-2)
    F['rating_rel'] = F.rating_f - F.groupby('ev').rating_f.transform('mean')
    for c in ['won_last3', 'runner_up_last', 't5_last', 'contend_l3', 'played_prev_wk', 'first_after_break', 'course_debut']:
        F[c] = F[c].fillna(False).astype(bool).astype(int)
    F['t5_in_l5'] = F.t5_in_l5.fillna(0); F['mc_in_l5'] = F.mc_in_l5.fillna(1)
    F['form_delta'] = (F.pct_l20 - F.pct_l5).fillna(0)          # + = recent finishes better than baseline
    F['course_rel'] = (0.5 - F.course_pct).fillna(0)             # + = finished high at this course before
    F['course_starts_c'] = F.course_starts.fillna(0).clip(upper=5)
    return F

def predict(F, models):
    X = F[FEATS].values.astype(float)
    out = {}
    for tgt, k in (('win', 1), ('t5', 5), ('t10', 10), ('t20', 20)):
        if tgt not in models: continue
        m = models[tgt]
        z = (X - np.array(m['mean'])) / np.array(m['scale'])
        p = 1 / (1 + np.exp(-(z @ np.array(m['coef']) + m['intercept'])))
        p = pd.Series(p, index=F.index)
        out[tgt] = (p * k / p.groupby(F.ev).transform('sum')).clip(upper=0.97)
    if 't10' in out: F['p_t10'], F['p_t20'] = out['t10'], out['t20']
    return out['win'], out['t5']

def fit(F):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    models = {}
    F = F.assign(t10=(F.fin <= 10).astype(int), t20=(F.fin <= 20).astype(int))
    for tgt in ('win', 't5', 't10', 't20'):
        sc = StandardScaler().fit(F[FEATS].values.astype(float))
        lr = LogisticRegression(C=0.5, max_iter=2000).fit(sc.transform(F[FEATS].values.astype(float)), F[tgt])
        models[tgt] = dict(mean=sc.mean_.tolist(), scale=sc.scale_.tolist(), coef=lr.coef_[0].tolist(), intercept=float(lr.intercept_[0]))
    return models

def reasons(row, models, n=3):
    """Top positive contributors for a player (feature value x coefficient, standardised)."""
    m = models['t5']; z = (row[FEATS].values.astype(float) - np.array(m['mean'])) / np.array(m['scale'])
    c = dict(zip(FEATS, z * np.array(m['coef'])))
    good = sorted([(v, f) for f, v in c.items() if v > 0.05 and f in LABELS], reverse=True)[:n]
    return ', '.join(LABELS[f] for _, f in good)

def load_training():
    F = pd.read_csv('data/features.csv', low_memory=False, parse_dates=['start'])
    F['key'] = key(F.player)
    Rt = pd.read_csv('data/ratings.csv')
    F = F.merge(Rt[['tour', 'event_id', 'key', 'rating']], on=['tour', 'event_id', 'key'], how='left')
    F = F[(F.start.dt.year >= 2021) & (F.fin.notna() | F.mc.astype(bool))]
    return prepare(F)

if __name__ == '__main__':
    F = load_training()
    tr, te = F[F.start.dt.year <= 2025], F[F.start.dt.year == 2026]
    models = fit(tr)
    te = te.copy(); te['pm_win'], te['pm_t5'] = predict(te, models)
    # compare with Betfair close where priced
    t = te[te.bf_win.notna()].copy()
    t['mk'] = 1 / t.bf_win; t['mk'] = t.mk / t.groupby('ev').mk.transform('sum')
    t['pm'] = t.pm_win / t.groupby('ev').pm_win.transform('sum')
    ll = lambda p, y: -np.mean(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1)))
    res = {'model': ll(t.pm, t.win), 'market': ll(t.mk, t.win)}
    for w in (0.1, 0.2, 0.3):
        b = np.exp((1 - w) * np.log(t.mk) + w * np.log(t.pm)); b = b / b.groupby(t.ev).transform('sum')
        res[f'blend {int(w*100)}% model'] = ll(b, t.win)
    print('2026 holdout win log-loss (lower = better), events:', t.ev.nunique()); [print(f'  {k:18s} {v:.5f}') for k, v in res.items()]
    # how often the winner is in the model's top 10
    te['rk'] = te.groupby('ev').pm_win.rank(ascending=False)
    print('winner in model top 10:', round((te[te.win == 1].rk <= 10).mean(), 2), '| top 5 finishers in model top 20:', round((te[te.t5 == 1].rk <= 20).mean(), 2))
    print('coefficients (t5):', {f: round(c, 2) for f, c in zip(FEATS, models['t5']['coef'])})
    os.makedirs('models', exist_ok=True)
    json.dump(fit(F), open('models/buildup.json', 'w'), indent=1)
    print('saved models/buildup.json (fit on 2021-26)')
