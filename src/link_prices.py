"""Link Betfair markets to ESPN events and players -> data/player_event.csv
One row per ESPN player-event with outcome and Betfair closing prices (win/top5/top10/top20)."""
import pandas as pd, numpy as np, re
from unidecode import unidecode
from rapidfuzz import fuzz, process
def norm(s): return re.sub(r'[^a-z ]', '', unidecode(str(s)).lower().replace('-', ' ')).strip()
E = pd.read_csv('data/events.csv'); R = pd.read_csv('data/results.csv', low_memory=False)
B = pd.read_csv('data/betfair_prices.csv').rename(columns={'event_id':'bf_event_id'})
E = E[E.status == 'STATUS_FINAL'].copy()
E['start_d'] = pd.to_datetime(E.start.str[:10]); E['end_d'] = pd.to_datetime(E.end.str[:10])
B['mt'] = pd.to_datetime(B.market_time.str[:10])
# tour tag from Betfair event name
def btour(n):
    n = str(n)
    if n.startswith('PGA'): return 'pga'
    if 'DPW' in n or 'DP World' in n: return 'eur'
    if re.search(r'Masters|US Open|U\.S\. Open|The Open|Open Championship|US PGA|PGA Championship', n) and not re.search(r'Champ|LPGA|Senior|Seniors|Legends', n.split(' 20')[0].replace('PGA Championship','')): return 'major'
    return None
mk = B.drop_duplicates('market_id')[['market_id','event_name','market_type','mt']].copy()
mk['bt'] = mk.event_name.map(btour)
mk = mk[mk.bt.notna()]
links = []
for _, m in mk.iterrows():
    cand = E[(E.start_d <= m.mt + pd.Timedelta(days=4)) & (E.end_d >= m.mt - pd.Timedelta(days=4))]
    if m.bt in ('pga', 'eur'): cand = cand[cand.tour == m.bt] if m.bt == 'eur' or (cand.tour == 'pga').any() else cand
    if cand.empty: continue
    nm = norm(re.sub(r'^(PGA|DPW Tour)\s*', '', m.event_name))
    sc = cand.name.map(lambda x: fuzz.token_set_ratio(nm, norm(x)))
    best = sc.idxmax()
    if sc[best] >= 55: links.append((m.market_id, m.market_type, cand.loc[best, 'tour'], cand.loc[best, 'event_id'], sc[best]))
L = pd.DataFrame(links, columns=['market_id','market_type','tour','event_id','score'])
P = B.merge(L[['market_id','tour','event_id']], on='market_id')
P['pn'] = P.runner.map(norm); R['pn'] = R.player.map(norm)
out = R.copy()
for mt, col in [('WINNER','bf_win'),('TOP_5_FINISH','bf_t5'),('TOP_10_FINISH','bf_t10'),('TOP_20_FINISH','bf_t20')]:
    q = P[P.market_type == mt].drop_duplicates(['tour','event_id','pn'])
    # exact normalised match, then fuzzy within event
    m1 = out.merge(q[['tour','event_id','pn','ltp_close']], on=['tour','event_id','pn'], how='left')
    out[col] = m1.ltp_close.values
    if mt == 'WINNER':
        m2 = out.merge(q[['tour','event_id','pn','ltp_72h']], on=['tour','event_id','pn'], how='left'); out['bf_win_72h'] = m2.ltp_72h.values
    miss = out[col].isna() & out.set_index(['tour','event_id']).index.isin(q.set_index(['tour','event_id']).index)
    for (t, e), g in out[miss].groupby(['tour','event_id']):
        names = q[(q.tour == t) & (q.event_id == e)]
        cho = dict(zip(names.pn, names.ltp_close))
        for ix, pn in g.pn.items():
            r = process.extractOne(pn, list(cho), scorer=fuzz.token_sort_ratio)
            if r and r[1] >= 85: out.at[ix, col] = cho[r[0]]
out.drop(columns='pn').to_csv('data/player_event.csv', index=False)
ev = L.groupby('market_type').event_id.nunique(); print('linked events by market:\n', ev)
w = out[out.pos == 1]; print('winners with bf_win price:', w.bf_win.notna().sum(), 'of', len(w[w.event_id.isin(L[L.market_type=='WINNER'].event_id)]))
