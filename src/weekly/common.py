import re, glob, os
import pandas as pd
from unidecode import unidecode
from rapidfuzz import process, fuzz

def norm(s):
    return ' '.join(re.sub(r'[^a-z ]', ' ', unidecode(str(s)).lower()).split())

def match_names(left, right, cutoff=86):
    """Map each name in `left` to the best name in `right` (normalised, fuzzy). Returns dict left->right."""
    rn = {norm(r): r for r in right}
    out = {}
    for l in left:
        k = norm(l)
        if k in rn: out[l] = rn[k]; continue
        m = process.extractOne(k, list(rn), scorer=fuzz.token_sort_ratio)
        if m and m[1] >= cutoff: out[l] = rn[m[0]]
    return out

def latest(pattern):
    files = sorted(glob.glob(pattern), key=os.path.getmtime)
    return files[-1] if files else None

# Ben's target-profit staking: stake so a win returns this profit
TARGET = {'WINNER': 500, 'TOP_5_FINISH': 100, 'TOP_10_FINISH': 75, 'TOP_20_FINISH': 50}
def stake_for(market, price):
    return round(TARGET.get(market, 50) / max(price - 1, 0.01), 2)
