"""Backfill points and comment counts of every thread a mention sits in (Algolia comments carry neither).
Uses the public HN Firebase API. Cached in data/cache/threads.json, safe to re-run."""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import requests

os.makedirs("data/cache", exist_ok=True)
CACHE = "data/cache/threads.json"
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
def save(d): json.dump(d, open(CACHE + ".tmp", "w")); os.replace(CACHE + ".tmp", CACHE)   # an interrupted run never leaves half a file
SETTLE = 14 * 86400                                  # a thread's points and comments are still moving for about two weeks
CACHE_TIME = os.path.getmtime(CACHE) if os.path.exists(CACHE) else 0   # entries cached before timestamps existed
for c in cache.values(): c.setdefault("fetched_at", int(CACHE_TIME))   # stamp entries cached before timestamps existed
def settled(c): return c["fetched_at"] - (c.get("time") or 0) >= SETTLE
need = set()
for l in open("data/mentions.jsonl"):
    m = json.loads(l)
    c = cache.get(str(m["story_id"])) if m["story_id"] else None
    if m["story_id"] and (c is None or not settled(c)): need.add(m["story_id"])
print(f"{len(need)} threads to fetch, {len(cache)} cached", file=sys.stderr)

def get(i):
    for a in range(4):
        try:
            r = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json", timeout=30)
            if r.ok:
                d = r.json()
                if not d: return i, None                   # deleted or not yet visible: try again next run
                return i, {"score": d.get("score") or 0, "descendants": d.get("descendants") or 0, "title": d.get("title"), "time": d.get("time"), "fetched_at": int(time.time())}
        except Exception:
            pass
        time.sleep(2 * (a + 1))
    return i, None

done = 0
with ThreadPoolExecutor(max_workers=16) as ex:
    for i, v in ex.map(get, sorted(need)):
        done += 1
        if v: cache[str(i)] = v
        if done % 1000 == 0:
            save(cache); print(f"{done}/{len(need)}", file=sys.stderr)
save(cache)
print(f"threads cached: {len(cache)}", file=sys.stderr)
