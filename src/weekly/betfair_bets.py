"""Import Ben's Betfair Exchange golf bets into bets/log.csv.
Settled bets (Betfair keeps the last 90 days via the API) come in with Betfair's own profit; matched bets
still running come in as pending and are settled later. Each row carries notes 'bf:<betId>' so nothing is
added twice. Returns are before Betfair commission. Uses the same secrets as betfair_live.py."""
import os, sys, datetime as dt
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from betfair_live import login, call

MT = {'WINNER': 'win', 'TOP_5_FINISH': 'top5', 'TOP_10_FINISH': 'top10', 'TOP_20_FINISH': 'top20'}
COLS = ['date', 'event', 'player', 'market', 'price', 'stake', 'book', 'notes', 'result_pos', 'settle', 'return', 'close_price', 'clv']

def market_of(desc, side):
    m = MT.get(desc.get('marketType'), (desc.get('marketDesc') or desc.get('marketType') or 'other').lower())
    return m if side == 'BACK' else f'lay {m}'

def main():
    tok = login()
    now = dt.datetime.now(dt.timezone.utc)
    settled, frm = [], 0
    while True:   # paged, max 1000 a call
        r = call(tok, 'listClearedOrders', {'betStatus': 'SETTLED', 'eventTypeIds': ['3'], 'includeItemDescription': True,
                                            'settledDateRange': {'from': (now - dt.timedelta(days=90)).isoformat()},
                                            'fromRecord': frm, 'recordCount': 1000})
        settled += r.get('clearedOrders', [])
        if not r.get('moreAvailable'): break
        frm += 1000
    cur = call(tok, 'listCurrentOrders', {'orderProjection': 'EXECUTABLE_AND_EXECUTION_COMPLETE'}).get('currentOrders', [])
    L = pd.read_csv('bets/log.csv', dtype=object) if os.path.exists('bets/log.csv') else pd.DataFrame(columns=COLS)
    for c in COLS:
        if c not in L: L[c] = ''
    L = L.fillna('')
    have = {n[3:]: i for i, n in L.notes.items() if str(n).startswith('bf:')}
    added = updated = 0
    for o in settled:
        d = o.get('itemDescription', {})
        if d.get('eventTypeDesc', 'Golf') != 'Golf': continue
        bid = str(o['betId'])
        row = dict(date=str(o.get('placedDate', ''))[:10], event=d.get('eventDesc', ''), player=d.get('runnerDesc', ''),
                   market=market_of(d, o.get('side')), price=o.get('priceMatched'), stake=o.get('sizeSettled'),
                   book='Betfair Exchange', notes='bf:' + bid, settle=o.get('betOutcome', '').lower(),
                   **{'return': round(float(o.get('profit', 0)), 2)})
        if bid in have:
            i = have[bid]
            if str(L.at[i, 'settle']) != row['settle'] or str(L.at[i, 'return']) != str(row['return']):
                for k in ('settle', 'return', 'price', 'stake'): L.at[i, k] = str(row[k])
                updated += 1
        else:
            L.loc[len(L)] = {**{c: '' for c in COLS}, **{k: str(v) for k, v in row.items()}}; have[bid] = len(L) - 1; added += 1
    # matched but not yet settled: add as pending (need the market catalogue for names)
    pend = [o for o in cur if float(o.get('sizeMatched', 0) or 0) > 0 and str(o['betId']) not in have]
    if pend:
        mids = sorted({o['marketId'] for o in pend})
        cat = []
        for i in range(0, len(mids), 50):
            cat += call(tok, 'listMarketCatalogue', {'filter': {'marketIds': mids[i:i + 50]}, 'maxResults': 200,
                                                    'marketProjection': ['EVENT', 'EVENT_TYPE', 'RUNNER_DESCRIPTION', 'MARKET_DESCRIPTION']})
        cm = {m['marketId']: m for m in cat}
        for o in pend:
            m = cm.get(o['marketId'])
            if not m or m.get('eventType', {}).get('id') != '3': continue
            names = {r['selectionId']: r['runnerName'] for r in m.get('runners', [])}
            desc = {'marketType': m.get('description', {}).get('marketType'), 'marketDesc': m.get('marketName')}
            L.loc[len(L)] = {**{c: '' for c in COLS}, 'date': str(o.get('placedDate', ''))[:10], 'event': m['event']['name'],
                             'player': names.get(o['selectionId'], ''), 'market': market_of(desc, o.get('side')),
                             'price': str(o.get('averagePriceMatched')), 'stake': str(o.get('sizeMatched')),
                             'book': 'Betfair Exchange', 'notes': 'bf:' + str(o['betId'])}
            added += 1
    L[COLS].to_csv('bets/log.csv', index=False)
    print(f'Betfair bets: {added} added, {updated} updated ({len(settled)} settled golf bets in the last 90 days, {len(pend)} pending)')

if __name__ == '__main__':
    main()
