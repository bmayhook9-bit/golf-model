"""Extract pre-tournament prices from Betfair BASIC historic golf files.
Usage: python betfair_extract.py RAW_DIR OUT_CSV
Markets kept: WINNER, TOP_5/10/20_FINISH. Prices are last traded price (ltp)
at close (first in-play or market time), 72h before and 7d before."""
import bz2, json, glob, csv, sys, os
from datetime import datetime
T = {'WINNER', 'TOP_5_FINISH', 'TOP_10_FINISH', 'TOP_20_FINISH'}

def at(hl, t):
    v = None
    for p, x in hl:
        if p <= t: v = x
        else: break
    return v

def main(raw, out):
    seen = set()
    w = csv.writer(open(out, 'w', newline=''))
    w.writerow(['market_id','event_id','event_name','market_type','market_time','open_date',
                'country','n_winners','runner_id','runner','status','ltp_close','ltp_72h','ltp_7d'])
    for f in sorted(glob.glob(os.path.join(raw, '**/1.*.bz2'), recursive=True)):
        mid = os.path.basename(f)[:-4]
        if mid in seen: continue          # same market downloaded twice
        mdl, names, hist, inplay = None, {}, {}, None
        try:
            with bz2.open(f, 'rt') as h:
                for line in h:
                    try: d = json.loads(line); pt = d['pt']
                    except Exception: continue
                    for m in d.get('mc', []):
                        if 'marketDefinition' in m:
                            mdl = m['marketDefinition']
                            for r in mdl['runners']: names[r['id']] = r.get('name')
                            if mdl.get('inPlay') and inplay is None: inplay = pt
                        for rc in m.get('rc', []):
                            if 'ltp' in rc: hist.setdefault(rc['id'], []).append((pt, rc['ltp']))
        except Exception:
            continue
        if not mdl or mdl.get('marketType') not in T: continue
        seen.add(mid)
        mt = int(datetime.fromisoformat(mdl['marketTime'].replace('Z', '+00:00')).timestamp() * 1000)
        cut = min(inplay or mt, mt)
        for r in mdl['runners']:
            hl = sorted(hist.get(r['id'], []))
            w.writerow([mid, mdl.get('eventId'), (mdl.get('eventName') or '').strip(), mdl['marketType'],
                        mdl['marketTime'], mdl.get('openDate'), mdl.get('countryCode'), mdl.get('numberOfWinners'),
                        r['id'], names.get(r['id']), r.get('status'),
                        at(hl, cut), at(hl, cut - 72*3600e3), at(hl, cut - 7*24*3600e3)])

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
