"""Fetch ESPN core event metadata (course, par, yards, holes, purse) for each raw event."""
import json, gzip, os, sys, glob, time, urllib.request
U = "https://sports.core.api.espn.com/v2/sports/golf/leagues/{t}/events/{i}?lang=en"
def get(u):
    for k in range(3):
        try:
            with urllib.request.urlopen(u, timeout=40) as r: return json.load(r)
        except Exception: time.sleep(2 + 3*k)
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
for f in sorted(glob.glob('raw/espn/*.json.gz')):
    t, y, i = os.path.basename(f).split('.')[0].split('_')
    fn = os.path.join(out, f"{t}_{i}.json")
    if os.path.exists(fn): continue
    d = get(U.format(t=t, i=i))
    if d:
        keep = {k: d.get(k) for k in ('id','name','date','endDate','courses','purse','isSignature','primary','playoffType','tournament')}
        json.dump(keep, open(fn, 'w')); time.sleep(0.2)
print('meta done', len(os.listdir(out)))
