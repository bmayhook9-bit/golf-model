"""Grade bets/log.csv: result, return, closing price (Betfair back, last snapshot before start), CLV.
market = win | top5 | top10 | top20. Dead heats settled pro rata."""
import sys, os, glob
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from common import norm, match_names
from rapidfuzz import fuzz
K = {'win': 1, 'top5': 5, 'top10': 10, 'top20': 20}
MT = {'win': 'WINNER', 'top5': 'TOP_5_FINISH', 'top10': 'TOP_10_FINISH', 'top20': 'TOP_20_FINISH'}

def closing_prices():
    fs = sorted(glob.glob('data/live/prices_*.csv'))
    if not fs: return pd.DataFrame()
    P = pd.concat(pd.read_csv(f) for f in fs)
    P['snapshot'] = pd.to_datetime(P.snapshot, utc=True)
    P['event'] = P.event.astype(str).str.strip()
    # Betfair moves marketStartTime to each round, so 'closing' = last snapshot taken before the market went in-play
    P = P[(P.in_play.astype(str).str.lower() != 'true') & P.back.notna()]
    return P.sort_values('snapshot').groupby(['event', 'market_type', 'runner']).tail(1)

def main():
    L = pd.read_csv('bets/log.csv', dtype=object)
    if L.empty: print('no bets logged'); return
    R = pd.read_csv('data/results.csv', low_memory=False); E = pd.read_csv('data/events.csv')
    E = E[E.status == 'STATUS_FINAL']; E['start_d'] = pd.to_datetime(E.start.str[:10])
    C = closing_prices()
    for col in ['result_pos', 'settle', 'return', 'close_price', 'clv']:
        if col not in L: L[col] = ''
        L[col] = L[col].fillna('').astype(object)
    for i, b in L.iterrows():
        d = pd.to_datetime(b.date)
        cand = E[(E.start_d >= d - pd.Timedelta(days=3)) & (E.start_d <= d + pd.Timedelta(days=7))]
        if not cand.empty:
            sc = cand.name.map(lambda n: fuzz.token_set_ratio(norm(b.event), norm(n)))
            ev = cand.loc[sc.idxmax()] if sc.max() >= 60 else None
        else: ev = None
        price, stake, k = float(b.price), float(b.stake), K.get(str(b.market).strip().lower(), 1)
        if ev is not None:
            F = R[(R.tour == ev.tour) & (R.event_id == ev.event_id)]
            m = match_names([b.player], F.player)
            if m:
                pos = F[F.player == m[b.player]].pos.iloc[0]
                if pd.isna(pos): share = 0.0; L.at[i, 'result_pos'] = 'MC'
                else:
                    c = (F.pos == pos).sum(); share = max(0, min(k, pos + c - 1) - pos + 1) / c
                    L.at[i, 'result_pos'] = f"T{int(pos)}" if c > 1 else str(int(pos))
                L.at[i, 'settle'] = str(round(share, 3)); L.at[i, 'return'] = str(round(share * stake * price - stake, 2))
        if not C.empty:
            c = C[C.market_type == MT.get(str(b.market).strip().lower())]
            c = c[c.event.map(lambda n: fuzz.token_set_ratio(norm(b.event), norm(n)) >= 60)]
            m = match_names([b.player], c.runner)
            if m:
                cp = c[c.runner == m[b.player]].back.iloc[-1]
                L.at[i, 'close_price'] = str(cp); L.at[i, 'clv'] = str(round(price / cp - 1, 3))
    L.to_csv('bets/log.csv', index=False)
    s = L[L['return'].astype(str).str.len() > 0]
    if len(s):
        st = s.stake.astype(float).sum(); rt = s['return'].astype(float).sum()
        cl = pd.to_numeric(L.clv, errors='coerce')
        print(f"Settled {len(s)} bets · staked £{st:.2f} · P/L £{rt:+.2f} · ROI {rt/st:+.1%} · avg CLV {cl.mean():+.1%} ({cl.notna().sum()} with close)")

if __name__ == '__main__':
    main()
