"""Snapshot Betfair Exchange golf prices for events starting in the next 7 days.
Needs env: BF_USERNAME, BF_PASSWORD, BF_APP_KEY (delayed key is fine).
Writes data/live/prices_<UTC timestamp>.csv
NOTE: written to Betfair's API-NG spec; first live run will confirm field names."""
import os, sys, json, datetime as dt, requests, pandas as pd
API = 'https://api.betfair.com/exchange/betting/rest/v1.0/'
MARKETS = ['WINNER', 'TOP_5_FINISH', 'TOP_10_FINISH', 'TOP_20_FINISH']

def login():
    for v in ('BF_USERNAME', 'BF_PASSWORD', 'BF_APP_KEY'):
        if not os.environ.get(v): sys.exit(f'Missing secret {v}')
    r = requests.post('https://identitysso.betfair.com/api/login',
                      data={'username': os.environ['BF_USERNAME'], 'password': os.environ['BF_PASSWORD']},
                      headers={'X-Application': os.environ['BF_APP_KEY'], 'Accept': 'application/json'}, timeout=30)
    try:
        j = r.json()
    except ValueError:
        try:
            geo = requests.get('https://ipinfo.io/json', timeout=10).json()
            where = f"{geo.get('city')}, {geo.get('country')}"
        except Exception:
            where = 'unknown'
        sys.exit(f"Betfair login returned non-JSON (HTTP {r.status_code}, runner location: {where}). "
                 f"First 300 chars: {r.text[:300]!r}")
    if j.get('status') != 'SUCCESS': sys.exit(f"Betfair login failed: {j.get('error')}")
    return j['token']

def call(token, op, params):
    r = requests.post(API + op + '/', json=params, timeout=60,
                      headers={'X-Application': os.environ['BF_APP_KEY'], 'X-Authentication': token,
                               'Content-Type': 'application/json', 'Accept': 'application/json'})
    r.raise_for_status(); return r.json()

def main():
    tok = login()
    now = dt.datetime.now(dt.timezone.utc)
    cat = call(tok, 'listMarketCatalogue', {
        'filter': {'eventTypeIds': ['3'], 'marketTypeCodes': MARKETS,
                   'marketStartTime': {'from': (now - dt.timedelta(days=1)).isoformat(),
                                       'to': (now + dt.timedelta(days=7)).isoformat()}},
        'marketProjection': ['EVENT', 'MARKET_START_TIME', 'RUNNER_DESCRIPTION', 'MARKET_DESCRIPTION'],
        'maxResults': 200})
    rows = []
    ids = [m['marketId'] for m in cat]
    books = []
    for i in range(0, len(ids), 10):   # keep request weight low
        books += call(tok, 'listMarketBook', {'marketIds': ids[i:i+10],
                      'priceProjection': {'priceData': ['EX_BEST_OFFERS']}})
    bk = {b['marketId']: b for b in books}
    for m in cat:
        names = {r['selectionId']: r['runnerName'] for r in m['runners']}
        b = bk.get(m['marketId'], {})
        for r in b.get('runners', []):
            ex = r.get('ex', {})
            back = (ex.get('availableToBack') or [{}])[0].get('price')
            lay = (ex.get('availableToLay') or [{}])[0].get('price')
            rows.append(dict(snapshot=now.isoformat(), event=m['event']['name'], event_id=m['event']['id'],
                             market_id=m['marketId'], market_type=m.get('description', {}).get('marketType'),
                             market_start=m.get('marketStartTime'), in_play=b.get('inplay'),
                             runner=names.get(r['selectionId']), status=r.get('status'),
                             back=back, lay=lay, ltp=r.get('lastPriceTraded')))
    os.makedirs('data/live', exist_ok=True)
    fn = f"data/live/prices_{now.strftime('%Y%m%dT%H%M')}.csv"
    pd.DataFrame(rows).to_csv(fn, index=False)
    print(fn, len(rows), 'rows,', len(cat), 'markets')

if __name__ == '__main__':
    main()
