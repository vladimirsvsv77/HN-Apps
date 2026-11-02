"""Fetch store metadata for every app in data/mentions.jsonl. Cached in data/cache/, safe to re-run."""
import json, os, sys, time, collections
from concurrent.futures import ThreadPoolExecutor
import requests
from google_play_scraper import app as play_app
from google_play_scraper.exceptions import NotFoundError
import ssl
ssl._create_default_https_context = ssl.create_default_context   # google_play_scraper turns certificate checks off on import: turn them back on

os.makedirs("data/cache", exist_ok=True)
ITUNES_CACHE = "data/cache/itunes.json"
PLAY_CACHE = "data/cache/play.json"
load = lambda p: json.load(open(p)) if os.path.exists(p) else {}
REFRESH_DAYS, RETRY_MISSING_DAYS = 7, 30          # store data goes stale: refetch listings weekly, retry missing apps monthly
NOW = time.time()
def stale(entry, ts):                                # half a day of slack so a weekly cron never lands a hair short
    age = (NOW - ts.get(entry, NOW)) / 86400
    return age >= (REFRESH_DAYS if entry_val(entry) is not None else RETRY_MISSING_DAYS) - 0.5
def save(p, d):
    json.dump(d, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)

mentions = [json.loads(l) for l in open("data/mentions.jsonl")]
ios_country = collections.defaultdict(collections.Counter)
ios_ids, pkgs = set(), set()
for m in mentions:
    if m["store"] == "ios":
        ios_ids.add(m["store_id"])
        for cc in m.get("countries") or [m["country"] or "us"]: ios_country[m["store_id"]][cc] += 1
    else:
        pkgs.add(m["store_id"])

# ---- iOS via iTunes Lookup (batched, no key) ----
itunes = load(ITUNES_CACHE)
TS_PATH = "data/cache/fetched_at.json"
TS = load(TS_PATH)                                 # "ios:<id>" / "android:<pkg>" -> unix time of last fetch
def entry_val(k): return itunes.get(k[4:]) if k.startswith("ios:") else play.get(k[8:])
for k in list(itunes): TS.setdefault("ios:" + k, NOW)
KEEP = ["trackId", "trackName", "artistName", "sellerName", "kind", "primaryGenreName", "genres", "averageUserRating",
        "userRatingCount", "artworkUrl512", "artworkUrl100", "formattedPrice", "price", "releaseDate",
        "currentVersionReleaseDate", "trackViewUrl", "screenshotUrls", "ipadScreenshotUrls", "description", "bundleId",
        "contentAdvisoryRating", "minimumOsVersion", "version"]

def lookup(ids, country):                           # list of results, or None when the request itself failed
    for i in range(5):
        try:
            r = requests.get("https://itunes.apple.com/lookup", params={"id": ",".join(ids), "country": country}, timeout=60)
            if r.status_code == 200: return r.json().get("results", [])
            if r.status_code == 400: return []     # not an Apple storefront code (en, uk...): no apps there, and no veto on the US answer
            print("itunes", r.status_code, file=sys.stderr)
        except (requests.RequestException, ValueError) as e:
            print("itunes error", e, file=sys.stderr)
        time.sleep(10 * (i + 1))
    return None
ANSWERED, FAILED = set(), set()                      # ids asked in a request that succeeded / failed this run

def run_itunes(todo, country):
    todo = sorted(todo)
    for i in range(0, len(todo), 150):
        batch = todo[i:i + 150]
        res = lookup(batch, country)
        if res is None: FAILED.update(batch); continue
        ANSWERED.update(batch)
        for x in res:
            tid = str(x.get("trackId"))
            if tid in batch:
                itunes[tid] = {k: x.get(k) for k in KEEP}; itunes[tid]["country"] = country; TS["ios:" + tid] = NOW
        save(ITUNES_CACHE, itunes)
        print(f"itunes {country}: {i + len(batch)}/{len(todo)} cached {len(itunes)}", file=sys.stderr)
        time.sleep(3.5)

play = load(PLAY_CACHE)
for k in list(play): TS.setdefault("android:" + k, NOW)
run_itunes([i for i in ios_ids if i not in itunes or stale("ios:" + i, TS)], "us")
# second pass: apps missing in US store, try the country the link pointed at
by_cc = collections.defaultdict(list)
for i in ios_ids:
    if TS.get("ios:" + i) != NOW and (i not in itunes or stale("ios:" + i, TS)):   # not returned by the US store this run
        ccs = set(ios_country[i]) | ({(itunes.get(i) or {}).get("country")} - {None})
        for cc in sorted(ccs - {"us"}): by_cc[cc].append(i)
for cc, ids in sorted(by_cc.items()):
    run_itunes([i for i in ids if TS.get("ios:" + i) != NOW], cc)
for i in ios_ids:                                   # asked this run but not returned: no longer on the store
    if i in ANSWERED and i not in FAILED and TS.get("ios:" + i) != NOW: itunes[i] = None; TS["ios:" + i] = NOW
save(ITUNES_CACHE, itunes); save(TS_PATH, TS)
print("itunes done: found", sum(1 for v in itunes.values() if v), "of", len(ios_ids), file=sys.stderr)

# ---- Android via google-play-scraper (HTML scrape, polite concurrency) ----
PKEEP = ["title", "developer", "developerId", "icon", "score", "ratings", "installs", "realInstalls", "genre", "genreId",
         "free", "price", "released", "updated", "screenshots", "description", "url", "appId", "contentRating", "version", "summary"]

def fetch_play(pkg):
    for i in range(4):
        try:
            a = play_app(pkg, lang="en", country="us")
            return pkg, {k: a.get(k) for k in PKEEP}
        except NotFoundError:
            return pkg, None
        except Exception as e:
            time.sleep(5 * (i + 1))
    return pkg, "retry"

todo = [p for p in pkgs if p not in play or stale("android:" + p, TS)]
done = 0
with ThreadPoolExecutor(max_workers=8) as ex:
    for pkg, res in ex.map(fetch_play, todo):
        done += 1
        if res != "retry": play[pkg] = res; TS["android:" + pkg] = NOW
        if done % 100 == 0:
            save(PLAY_CACHE, play); print(f"play: {done}/{len(todo)}", file=sys.stderr)
save(PLAY_CACHE, play); save(TS_PATH, TS)
print("play done: found", sum(1 for v in play.values() if v), "of", len(pkgs), file=sys.stderr)
