"""Pull HN items since the ClickHouse dump ends (2023-08-18) that mention store links, via the Algolia HN API."""
import json, os, sys, time
import requests

os.makedirs("data/raw", exist_ok=True)
OUT = "data/raw/algolia_items.jsonl"
START = 1692316811  # 2023-08-18 03:40:11 UTC
END = int(time.time())
QUERIES = ["apps.apple.com", "itunes.apple.com", "play.google.com", "market.android.com", "market://details?id="]
API = "https://hn.algolia.com/api/v1/search_by_date"
seen = {}

def search(q, tag, a, b):
    for i in range(5):
        r = requests.get(API, params={"query": q, "tags": tag, "hitsPerPage": 1000,
                                      "numericFilters": f"created_at_i>={a},created_at_i<{b}"}, timeout=60)
        if r.status_code == 200:
            return r.json()
        print("algolia", r.status_code, r.text[:100], file=sys.stderr)
        time.sleep(3 * (i + 1))
    raise RuntimeError("algolia failed")

def pull(q, tag, a, b):
    d = search(q, tag, a, b)
    if d["nbHits"] >= 1000 and b - a > 3600:
        m = (a + b) // 2
        pull(q, tag, a, m); pull(q, tag, m, b)
        return
    for h in d["hits"]:
        seen.setdefault(h["objectID"], h)

month = 30 * 86400
for q in QUERIES:
    for tag in ("comment", "story"):
        a = START
        while a < END:
            b = min(a + month, END)
            pull(q, tag, a, b)
            a = b
        print(q, tag, "total so far", len(seen), file=sys.stderr)

with open(OUT, "w") as f:
    for h in seen.values():
        f.write(json.dumps(h) + "\n")
print("wrote", OUT, len(seen), file=sys.stderr)
