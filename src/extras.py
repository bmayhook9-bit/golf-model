"""Extra desk data:
  1. data/out/lead_history.csv  - every qualifier for the tracked lead (PGA, Betfair close < 20.0, won in last 3)
  2. data/out/frl.csv           - first-round leader / top 5 after round 1 for this week's event(s), Monte Carlo
  3. data/out/frl_backtest.json - calibration of the round-1 model on past PGA/DPWT events
Run after features.py, ratings.py and the weekly shortlist."""
import json, os, re, sys
import numpy as np, pandas as pd
from unidecode import unidecode
sys.path.insert(0, 'src')

def key(s): return ' '.join(re.sub(r'[^a-z ]', ' ', unidecode(str(s)).lower()).split())
COMM = 0.02          # Betfair commission on net winnings (basic rate is 5%; many UK accounts pay 2% on the discount scheme)
SIMS = 20000
rng = np.random.default_rng(7)

# ---------------- 1. tracked lead history ----------------
F = pd.read_csv('data/features.csv', low_memory=False)
LH = 'data/out/lead_history.csv'
cols = ['date', 'name', 'player', 'bf_win', 'bf_win_72h', 'clv_72h', 'fin', 'won', 'pl_1', 'stake_500', 'pl_500', 'sample']

def lead_rows(q):
    q = q.copy()
    q['date'] = q.start.str[:10]
    q['fin'] = [str(int(f)) if f == f else ('MC' if m else '') for f, m in zip(q.fin, q.mc.astype(bool))]
    q['won'] = q.win.fillna(0).astype(int)
    q['pl_1'] = np.where(q.won == 1, (q.bf_win - 1) * (1 - COMM), -1.0)            # £1 level stake at the close
    q['stake_500'] = (500 / (q.bf_win - 1)).round(2)                                  # Ben's target-profit staking
    q['pl_500'] = np.where(q.won == 1, 500 * (1 - COMM), -q.stake_500).round(2)
    if 'bf_win_72h' not in q: q['bf_win_72h'] = np.nan
    q['clv_72h'] = (q.bf_win_72h / q.bf_win - 1).round(3)                             # value of betting 72h out vs the close
    q['sample'] = np.where(q.date < '2026-01-01', 'research (2023-25)', 'holdout (2026)')
    q.loc[q.date >= '2026-11-16', 'sample'] = 'live (tracked)'
    return q[cols]

if 'bf_win' in F and F.bf_win.notna().any():
    # full history from the Betfair historic files (only on a machine that has data/player_event.csv)
    q = lead_rows(F[(F.tour == 'pga') & (F.bf_win < 20) & (F.won_last3 == True)])
else:
    # GitHub runner: no historic Betfair file. Keep the saved history and add new events from the live price snapshots.
    q = pd.read_csv(LH) if os.path.exists(LH) else pd.DataFrame(columns=cols)
    try:
        sys.path.insert(0, 'src/weekly'); from grade import closing_prices; from common import match_names
        from rapidfuzz import fuzz
        C = closing_prices(); C = C[(C.market_type == 'WINNER') & C.event.astype(str).str.startswith('PGA')]
        last = q.date.max() if len(q) else '2026-11-01'
        new = F[(F.tour == 'pga') & (F.start.str[:10] > last) & F.fin.notna() | (F.tour == 'pga') & (F.start.str[:10] > last) & F.mc.astype(bool)]
        add = []
        for (eid, nm), g in new.groupby(['event_id', 'name']):
            c = C[C.event.map(lambda n: fuzz.token_set_ratio(str(nm), str(n).replace('PGA ', '')) >= 70)]
            if c.empty: continue
            mp = match_names(list(g.player), list(c.runner)); bk = dict(zip(c.runner, c.back))
            g = g.copy(); g['bf_win'] = g.player.map(lambda p: bk.get(mp.get(p)))
            add.append(g[(g.bf_win < 20) & (g.won_last3 == True)])
        if add: q = pd.concat([q, lead_rows(pd.concat(add))], ignore_index=True)
    except Exception as ex:
        print('lead history: live top-up skipped:', ex)
q = q.sort_values('date'); q[cols].to_csv(LH, index=False)
print(f"lead: {len(q)} bets, {int(q.won.sum())} wins v {(1 / q.bf_win).sum():.1f} expected, £1 level P/L {q.pl_1.sum():+.1f}")

# ---------------- 2. round-1 model ----------------
R = pd.read_csv('data/results.csv', low_memory=False); E = pd.read_csv('data/events.csv')
R = R.merge(E[['tour', 'event_id', 'start', 'course', 'status']], on=['tour', 'event_id'])
R = R[(R.status == 'STATUS_FINAL') & R.r1.notna()].copy()
R['key'] = R.player.map(key)
R['rel1'] = R.r1 - R.groupby(['tour', 'event_id']).r1.transform('mean')
RT = pd.read_csv('data/ratings.csv')
R = R.merge(RT[['tour', 'event_id', 'key', 'rating']], on=['tour', 'event_id', 'key'], how='left')

def fill_rating(r):
    lo = r.quantile(0.1) if r.notna().any() else -2
    return r.fillna(lo if lo == lo else -2)

# residual spread of a round-1 score around the rating, and per-course scale
R['rf'] = R.groupby(['tour', 'event_id']).rating.transform(fill_rating)
R['res'] = R.rel1 + (R.rf - R.groupby(['tour', 'event_id']).rf.transform('mean'))
recent = R[R.start >= '2023-01-01']
SIG = float(recent.res.std())
csd = recent.groupby(['tour', 'course']).res.agg(['std', 'count'])
csd = csd[csd['count'] >= 200]
CSCALE = (csd['std'] / SIG).clip(0.85, 1.2).to_dict()
print(f"round-1 sigma {SIG:.2f} strokes; course scales for {len(CSCALE)} courses")

def simulate(ratings, sigma, sims=SIMS):
    """ratings: array (higher = better). Returns dead-heat shares: lead after R1, top 5 after R1, top 10 after R1."""
    n = len(ratings)
    s = np.rint(-ratings[None, :] + rng.normal(0, sigma, (sims, n)))
    best = s.min(1, keepdims=True)
    lead = (s == best); tied = lead.sum(1, keepdims=True)
    p_lead = (lead / tied).mean(0)
    out = [p_lead]
    A = np.empty_like(s); T = np.empty_like(s)
    for i in range(0, sims, 400):                        # strictly-better count and tie count per player, in chunks
        c = s[i:i + 400]
        A[i:i + 400] = (c[:, None, :] < c[:, :, None]).sum(2); T[i:i + 400] = (c[:, None, :] == c[:, :, None]).sum(2)
    for k in (5, 10):                                    # dead heat share = clip(k - better, 0, tied) / tied
        out.append((np.clip(k - A, 0, T) / T).mean(0))
    return out

# ---- shrink: ratings overstate round-1 skill gaps (one round is noisy); fit a multiplier on 2023-24 events ----
fit_ev = [g for _, g in R[(R.start >= '2023-01-01') & (R.start < '2025-01-01')].groupby(['tour', 'event_id']) if len(g) >= 60]
best = None
for k in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
    ll = 0.0
    for g in fit_ev:
        pl = simulate(k * g.rf.values, SIG * CSCALE.get((g.tour.iloc[0], g.course.iloc[0]), 1.0), 1500)[0]
        srt = np.sort(g.r1.values); a = np.searchsorted(srt, g.r1.values, 'left'); tt = np.searchsorted(srt, g.r1.values, 'right') - a
        w = np.where(a == 0, 1 / tt, 0); ll -= float((w * np.log(np.clip(pl, 1e-4, 1))).sum())
    if best is None or ll < best[1]: best = (k, ll)
SHRINK = best[0]; print('rating shrink for round 1:', SHRINK)

# ---- backtest calibration on 2025-26 events (pre-event ratings only, shrink fitted on 2023-24) ----
bt = []
for (t, e), g in R[R.start >= '2025-01-01'].groupby(['tour', 'event_id']):
    if len(g) < 60: continue
    sc = CSCALE.get((t, g.course.iloc[0]), 1.0)
    pl, p5, p10 = simulate(SHRINK * g.rf.values, SIG * sc, 4000)
    srt = np.sort(g.r1.values); a = np.searchsorted(srt, g.r1.values, 'left'); tt = np.searchsorted(srt, g.r1.values, 'right') - a
    bt.append(pd.DataFrame({'tour': t, 'p_lead': pl, 'p5': p5, 'a_lead': np.where(a == 0, 1 / tt, 0), 'a5': np.clip(5 - a, 0, tt) / tt, 'n': len(g)}))
BT = pd.concat(bt)
def calib(p, a, bins):
    b = pd.cut(BT[p], bins); g = BT.groupby(b, observed=True)
    return [dict(bin=str(i), n=int(len(x)), pred=round(float(x[p].sum()), 1), actual=round(float(x[a].sum()), 1)) for i, x in g]
naive_ll = lambda: None
res = dict(sigma=round(SIG, 2), shrink=SHRINK, events=int(BT.groupby(['tour', 'n']).ngroups),
           lead=calib('p_lead', 'a_lead', [0, .005, .01, .02, .04, 1]), top5=calib('p5', 'a5', [0, .02, .05, .1, .2, 1]))
# skill check: share of actual leaders' credit captured vs a model that gives everyone the same chance
BT['u_lead'] = 1 / BT.n
res['lead_lift_top_decile'] = round(float(BT[BT.p_lead >= BT.p_lead.quantile(0.9)].a_lead.sum() / BT[BT.p_lead >= BT.p_lead.quantile(0.9)].p_lead.sum()), 2)
json.dump(res, open('data/out/frl_backtest.json', 'w'), indent=1)
print('backtest', json.dumps(res['lead']), json.dumps(res['top5']))

# ---- this week's events ----
import buildup_model as BM
cur = BM.current_ratings()
B = pd.read_csv('data/out/buildup.csv') if os.path.exists('data/out/buildup.csv') else pd.DataFrame()
rows = []
for ev, g in (B.groupby('event', sort=False) if len(B) else []):
    tour = g.tour.iloc[0] if 'tour' in g else 'pga'
    from rapidfuzz import fuzz
    nm = key(str(ev).replace('PGA ', '').replace('DPW Tour ', ''))
    s2 = E.name.map(lambda n: fuzz.token_set_ratio(nm, key(n)))
    course = E.loc[s2.idxmax(), 'course'] if s2.max() >= 70 else None
    sc = CSCALE.get((tour, course), 1.0)
    rt = pd.Series([cur.get(BM.key(pd.Series([p])).iloc[0], np.nan) for p in g.player], dtype=float)
    rt = fill_rating(rt)
    pl, p5, p10 = simulate(SHRINK * rt.values, SIG * sc)
    for p, r, a, b, c in zip(g.player, rt, pl, p5, p10):
        rows.append(dict(event=ev, tour=tour, course=course, sigma=round(SIG * sc, 2), player=p, rating=round(float(r), 2),
                         p_r1_lead=round(float(a), 4), p_r1_t5=round(float(b), 4), p_r1_t10=round(float(c), 4)))
pd.DataFrame(rows).to_csv('data/out/frl.csv', index=False)
print('frl rows', len(rows))
