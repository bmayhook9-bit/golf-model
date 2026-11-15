"""Course profiles: slope (shots gained per 1-shot rating gap, top 60 rated), scoring by round,
winner position after 54 holes. -> data/course_profiles.csv"""
import pandas as pd, numpy as np
F = pd.read_csv('data/features.csv', low_memory=False, parse_dates=['start'])
F['key'] = F.player.str.lower().str.normalize('NFKD').str.encode('ascii','ignore').str.decode('ascii')
Rt = pd.read_csv('data/ratings.csv')
D = F.merge(Rt, on=['tour','event_id','key'], how='left')
D = D[D.start.dt.year >= 2021]
D['top60'] = D.groupby(['tour','event_id']).rating.rank(ascending=False) <= 60
out = []
for (t, c), g in D[D.rating.notna() & D.top60].groupby(['tour','course']):
    if g.event_id.nunique() < 3: continue
    # demean within event so the slope compares players inside the same week
    x = g.rating - g.groupby('event_id').rating.transform('mean')
    y = g.event_rel - g.groupby('event_id').event_rel.transform('mean')
    b = np.polyfit(x, y, 1)[0]
    n = len(g); se = np.sqrt(np.sum((y - b * x) ** 2) / (n - 2) / np.sum(x ** 2))
    allc = F[(F.tour == t) & (F.course == c)]
    r = {f'r{k}_avg': (allc[f'r{k}'] - allc.par).mean() for k in (1, 2, 3, 4)}
    w = allc[allc.fin == 1]
    out.append(dict(tour=t, course=c, editions=g.event_id.nunique(), slope=round(b, 2), slope_se=round(se, 2),
                    **{k: round(v, 2) for k, v in r.items()},
                    winner_led54=round((w.pos54 == 1).mean(), 2)))
P = pd.DataFrame(out).sort_values('slope', ascending=False)
P.to_csv('data/course_profiles.csv', index=False)
print(len(P), 'courses; median slope', P.slope.median())
print(P[P.tour=='eur'].head(8).to_string()); print(P[P.course.str.contains('Earth|Wentworth|Valderrama', na=False)].to_string())
