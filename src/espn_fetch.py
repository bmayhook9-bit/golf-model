"""Fetch ESPN golf scoreboards per event (raw JSON, gzipped).
Usage: python espn_fetch.py OUT_DIR [tour ...] (tours: pga eur)"""
import json, gzip, os, sys, time, urllib.request
BASE = "https://site.api.espn.com/apis/site/v2/sports/golf/{t}/scoreboard"
def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=40) as r: return json.load(r)
        except Exception as e:
            time.sleep(2 + 3*i)
    return None
def main(out, tours, years):
    for t in tours:
        for y in years:
            cal = (get(BASE.format(t=t) + f"?dates={y}") or {}).get('leagues', [{}])[0].get('calendar', [])
            for e in cal:
                fn = os.path.join(out, f"{t}_{y}_{e['id']}.json.gz")
                if os.path.exists(fn): continue
                s, en = e['startDate'][:10].replace('-', ''), e['endDate'][:10].replace('-', '')
                d = get(BASE.format(t=t) + f"?dates={s}-{en}")
                if not d: print('fail', t, e['id']); continue
                evs = [x for x in d.get('events', []) if x.get('id') == e['id']]
                if not evs: continue
                json.dump(evs[0], gzip.open(fn, 'wt'))
                time.sleep(0.3)
            print(t, y, len(cal), flush=True)
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:] or ['pga', 'eur'], range(2019, 2027))
