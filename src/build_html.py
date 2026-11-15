"""Build the interactive dashboard: data bundle + app/dashboard.html template -> dist/dashboard.html
Run after the weekly shortlist (needs data/out/*, data/results.csv, data/events.csv, data/ratings.csv, data/features.csv if present)."""
import json, glob, os, re, math
import numpy as np, pandas as pd
from unidecode import unidecode

def key(s): return ' '.join(re.sub(r'[^a-z ]', ' ', unidecode(str(s)).lower()).split())
def rd(x, n=3):
    try:
        return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), n)
    except Exception: return None
def rcsv(p):
    try: return pd.read_csv(p, low_memory=False) if os.path.exists(p) and os.path.getsize(p) > 2 else pd.DataFrame()
    except pd.errors.EmptyDataError: return pd.DataFrame()

D = {}
D['meta'] = json.load(open('data/out/meta.json')) if os.path.exists('data/out/meta.json') else {}
E = pd.read_csv('data/events.csv'); R = pd.read_csv('data/results.csv', low_memory=False)
E['date'] = E.start.str[:10]
H = R.merge(E[['tour', 'event_id', 'name', 'course', 'date', 'status', 'par']], on=['tour', 'event_id'])
H = H[H.status == 'STATUS_FINAL']; H['k'] = H.player.map(key)
H['fin'] = np.where(H.pos.notna(), H.pos.fillna(0).astype(int).astype(str), np.where(H.made_cut == False, 'MC', ''))

# ---------- this week's events ----------
B, T, V, L = rcsv('data/out/buildup.csv'), rcsv('data/out/targets.csv'), rcsv('data/out/value.csv'), rcsv('data/out/lead.csv')
events = []
for ev, g in (B.groupby('event', sort=False) if not B.empty else []):
    g = g.copy(); g['k'] = g.player.map(key)
    tk = {key(p): r for p, r in zip(T.player, T.to_dict('records'))} if not T.empty else {}
    lk = set(L[L.event == ev].player.map(key)) if not L.empty else set()
    rows = []
    for r in g.to_dict('records'):
        t = tk.get(r['k'], {})
        rows.append(dict(p=r['player'], k=r['k'], rank=int(r['rank']), mw=rd(r['model_win'], 4), m5=rd(r['model_top5'], 4),
                         m10=rd(r.get('model_top10'), 4), m20=rd(r.get('model_top20'), 4),
                         bf=rd(r['betfair_back'], 2), isn=rd(t.get('isn_fair'), 1), isnr=t.get('isn_rank'),
                         l3=r.get('last3') if isinstance(r.get('last3'), str) else '', why=r.get('why') if isinstance(r.get('why'), str) else '',
                         lead=r['k'] in lk))
    # course for the event: best name match among past events
    from rapidfuzz import fuzz
    nm = key(str(ev).replace('PGA ', '').replace('DPW Tour ', ''))
    sc = E.name.map(lambda n: fuzz.token_set_ratio(nm, key(n)))
    crs = E.loc[sc.idxmax(), 'course'] if len(sc) and sc.max() >= 70 else None
    nm_out = str(ev).strip(); nm_out = nm_out.title().replace('Rsm', 'RSM') if nm_out == nm_out.lower() else nm_out
    events.append(dict(name=nm_out, tour=g.tour.iloc[0], course=crs, players=rows))
# ISN skill notes for the week (ranks are within the ISN field; lower = better)
isn_fn = sorted(glob.glob('inbox/isn/*.csv'), key=os.path.getmtime)
ISK = {}
if isn_fn:
    I = pd.read_csv(isn_fn[-1])
    keep = [c for c in ['OTT Rank', 'Distance Rank', 'Accuracy Rank', 'APP Rank', 'APP 50-100 Rank', 'APP 100-150 Rank', 'APP 150-200 Rank',
                        'APP 200+ Rank', 'ARG Rank', 'Putting Total Rank', 'Bermuda Rank', 'Comp Courses Rank', 'Course History Rank', 'Course Fit ADJ']
            if c in I.columns]
    D['isn_cols'] = keep; D['isn_n'] = int(len(I))
    I['_p'] = 100 / (I['Win Odds'] + 100); I['_p'] = I._p / I._p.sum()     # ISN fair win probability, margin-free
    ISNP = {key(p): (1 / q, int(rk)) for p, q, rk in zip(I.Player, I._p, I['Model Rank']) if q == q}
    for r in I.to_dict('records'):
        ISK[key(r['Player'])] = [rd(r[c], 2) for c in keep]
else:
    ISNP = {}
for e in events:
    for r in e['players']:
        if r['k'] in ISK: r['sk'] = ISK[r['k']]
        if e['tour'] == 'pga' and r['k'] in ISNP:            # ISN covers the PGA Tour: fair price + rank for every player
            r['isn'] = rd(ISNP[r['k']][0], 1); r['isnr'] = ISNP[r['k']][1]
D['events'] = events

# ---------- players (anyone who played since 2025) ----------
recent = H[H.date >= '2025-01-01'].k.unique()
Rt = rcsv('data/ratings.csv')
Rt = Rt.merge(E[['tour', 'event_id', 'date']], on=['tour', 'event_id']) if not Rt.empty else Rt
cur = rcsv('data/out/ratings_current.csv')
curd = dict(zip(cur.key.map(key), cur.rating)) if not cur.empty else {}
players = {}
for k, h in H[H.k.isin(recent)].sort_values('date').groupby('k'):
    hh = h.tail(25)
    rs = Rt[Rt.key.map(key) == k].sort_values('date').tail(40) if not Rt.empty else pd.DataFrame()
    players[k] = dict(n=h.player.iloc[-1], r=rd(curd.get(k), 2),
                      s=[[d, t, n, c, f] for d, t, n, c, f in zip(hh.date, hh.tour, hh.name, hh.course.fillna(''), hh.fin)],
                      rt=[[d, rd(v, 2)] for d, v in zip(rs.date, rs.rating)] if len(rs) else [])
# course history counts for every course (all years) per player, compact
ch = H[H.k.isin(recent)].groupby(['k', 'course']).fin.apply(lambda s: ' '.join(s.astype(str))).reset_index()
for r in ch.itertuples():
    players[r.k].setdefault('c', {})[r.course] = r.fin
D['players'] = players

# ---------- courses ----------
CP = rcsv('data/out/course_profiles.csv')
med = CP.groupby('tour').slope.median().to_dict() if not CP.empty else {}
courses = {}
holes = {}
for f in glob.glob('raw/meta/pga_*.json'):
    m = json.load(open(f)); c = (m.get('courses') or [{}])[0]
    if c.get('holes') and c.get('name'): holes[c['name']] = {h['number']: (h.get('shotsToPar'), h.get('totalYards')) for h in c['holes']}
HS = rcsv('data/holes.csv')
if not HS.empty:
    HS = HS.merge(E[['tour', 'event_id', 'course']], on=['tour', 'event_id'])
for r in (CP.to_dict('records') if not CP.empty else []):
    c = r['course']
    w = H[(H.course == c) & (H.pos == 1)].sort_values('date', ascending=False)
    hl = []
    if c in holes and not HS.empty:
        hs = HS[HS.course == c].groupby('hole').strokes.mean()
        for n, (par, yds) in sorted(holes[c].items()):
            if n in hs.index and par: hl.append([int(n), int(par), int(yds or 0), rd(hs[n] - par, 3)])
    courses[c] = dict(tour=r['tour'], ed=int(r['editions']), slope=rd(r['slope'], 2), se=rd(r['slope_se'], 2), med=rd(med.get(r['tour']), 2),
                      rounds=[rd(r[f'r{i}_avg'], 2) for i in (1, 2, 3, 4)], led54=rd(r['winner_led54'], 2),
                      winners=[[d[:4], p, int(t) if t == t else None] for d, p, t in zip(w.date, w.player, w.total)][:10], holes=hl)
D['courses'] = courses

# ---------- winners case studies ----------
C = rcsv('data/out/case_studies.csv')
D['winners'] = [dict(d=str(r['start'])[:10], e=r['name'], p=r['player'], bf=rd(r['bf_win'], 1), mr=rd(r['mkt_rank'], 0), mo=rd(r['model_rank'], 0),
                     rr=rd(r['rating_rank'], 0), f=int(r['field']), l5=r['last5'] if isinstance(r['last5'], str) else '',
                     b=r['build_up'] if isinstance(r['build_up'], str) else '') for r in C.to_dict('records')] if not C.empty else []

# ---------- trends: pattern explorer (singles + pairs) ----------
NAMES = {'won_last3': 'Won in last 3', 'runner_up_last': 'Runner-up last start', 't5_last': 'Top 5 last start', 't5_2p': '2+ top 5s in last 5',
         'contend_l3': 'Contended in last 3', 'played_prev_wk': 'Played week before', 'first_after_break': 'First start after break',
         'mc_last': 'Missed cut last start', 'course_good': 'Strong course history', 'course_debut': 'Course debut', 'fav20': 'Priced under 20.0',
         'pga': 'PGA Tour event'}
pat = json.load(open('data/out/patterns.json')) if os.path.exists('data/out/patterns.json') else None
if pat is None and os.path.exists('data/features.csv'):
    F = pd.read_csv('data/features.csv', low_memory=False, parse_dates=['start'])
    F = F[(F.start.dt.year >= 2021) & (F.fin.notna() | F.mc.astype(bool))].copy()
    F['t5_2p'] = F.t5_in_l5 >= 2; F['fav20'] = F.bf_win < 20 if 'bf_win' in F else False; F['pga'] = F.tour == 'pga'
    for c in NAMES: F[c] = F[c].fillna(False).astype(bool)
    pr = F[F.bf_win.notna()].copy() if 'bf_win' in F else F.iloc[0:0]
    if len(pr):
        pr['p'] = 1 / pr.bf_win; pr['p'] = pr.p / pr.groupby(['tour', 'event_id']).p.transform('sum'); pr['ret'] = np.where(pr.win == 1, pr.bf_win - 1, -1)
    keys = list(NAMES); combos = [(a,) for a in keys] + [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]]
    out = []
    w = F[F.win == 1]
    for cb in combos:
        # prices only exist from 2023: a combo using price compares within 2023-26 only
        FF = F[F.bf_win.notna()] if 'fav20' in cb else F
        ww = FF[FF.win == 1]
        mf = np.logical_and.reduce([FF[c] for c in cb]); mw = np.logical_and.reduce([ww[c] for c in cb])
        d = dict(c=list(cb), wp=rd(mw.mean() * 100, 1), fp=rd(mf.mean() * 100, 2), wn=int(mw.sum()), fn=int(mf.sum()))
        if len(pr):
            mp = np.logical_and.reduce([pr[c] for c in cb]); x = pr[mp]
            if len(x) >= 20:
                d.update(pa=int(x.win.sum()), pe=rd(x.p.sum(), 1), roi=rd(x.ret.mean(), 3), pn=int(len(x)))
        out.append(d)
    pat = dict(names=NAMES, combos=out)
    json.dump(pat, open('data/out/patterns.json', 'w'))
D['patterns'] = pat or {'names': NAMES, 'combos': []}

# ---------- bets ----------
bl = rcsv('bets/log.csv')
D['bets'] = json.loads(bl.to_json(orient='records')) if not bl.empty else []
D['study_url'] = 'https://claude.ai/artifact/8BoouiLV4UdX3DWW97mCGu'

js = json.dumps(D, separators=(',', ':'), ensure_ascii=False)
html = open('app/dashboard.html').read().replace('/*__DATA__*/null', js)
os.makedirs('dist', exist_ok=True)
open('dist/dashboard.html', 'w').write(html)
print('dist/dashboard.html', round(len(html) / 1e6, 2), 'MB ·', len(events), 'events ·', len(players), 'players ·', len(courses), 'courses')
