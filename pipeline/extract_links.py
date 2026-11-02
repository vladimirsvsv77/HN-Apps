"""Turn raw HN items into one row per (item, app) mention. Output: data/mentions.jsonl"""
import json, re, html, sys, os
from collections import OrderedDict

URL_RE = re.compile(r"(?:https?|itms-apps|itms-appss|itms)://(?:(?:[a-z0-9-]+\.)?itunes\.apple\.com|apps\.apple\.com|play\.google\.com|market\.android\.com)[^\s\"'<>)\]\\]*|market://details\?[^\s\"'<>)\]\\]*", re.I)
APPLE_ID_RE = re.compile(r"/id(\d{6,12})|viewSoftware\?(?:[^&\s]*&)*id=(\d{6,12})", re.I)
APPLE_SKIP = ("/developer/", "/app-bundle/", "/podcast/", "/album/", "/book/", "/movie/", "/tv-season/", "/audiobook/", "/music-video/", "/genre/", "/collection/", "/story/", "/artist/", "/playlist/", "/curator/")
PLAY_PKG_RE = re.compile(r"/(?:store/apps/)?details(?:/[^?\s#]*)?\?(?:[^&\s#]*&)*id=([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+)", re.I)   # play.google.com/store/apps/details and legacy market.android.com/details
TAG_RE = re.compile(r"<[^>]+>")
A_RE = re.compile(r'<a\s+href="([^"]+)"[^>]*>.*?</a>', re.S)

def plain(s):
    if not s: return ""
    s = s.replace("<p>", "\n\n").replace("<br>", "\n")
    s = A_RE.sub(lambda m: m.group(1), s)   # HN truncates link text; keep the full href
    s = TAG_RE.sub("", s)
    return html.unescape(s).strip()

def find_apps(text):
    found = OrderedDict()
    for m in URL_RE.finditer(html.unescape(text or "")):
        u = m.group(0)
        if u.endswith("...") or u.endswith("\u2026"): continue  # HN truncates displayed link text
        u = u.rstrip(".,;:!?")
        low = u.lower()
        if "apple.com" in low:
            if any(s in low for s in APPLE_SKIP): continue
            idm = APPLE_ID_RE.search(u)
            if not idm: continue
            aid = idm.group(1) or idm.group(2)
            cc = re.search(r"apple\.com/([a-z]{2})/", low)
            key = f"ios:{aid}"
            f = found.setdefault(key, {"store": "ios", "store_id": aid, "url": u, "country": cc.group(1) if cc else None,
                                       "mac_hint": "mt=12" in low or "/mac/" in low, "countries": []})
            c2 = cc.group(1) if cc else "us"
            if c2 not in f["countries"]: f["countries"].append(c2)
        else:
            pm = PLAY_PKG_RE.search(u)
            if not pm: continue
            pkg = pm.group(1)
            found.setdefault(f"android:{pkg}", {"store": "android", "store_id": pkg, "url": u, "country": None, "mac_hint": False})
    return found

def excerpt(text, limit=1500):
    t = plain(text)
    return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0] + " …"

mentions = {}
def add(item_id, typ, by, ts, text, title, url, story, comments=0, src="al"):
    body = (text or "") + " " + (url or "")
    for key, info in find_apps(body).items():
        k = (item_id, key)
        if k in mentions: continue
        mentions[k] = {"item_id": item_id, "type": typ, "by": by, "time": ts, "app_key": key, **info,
                       "title": title or None, "text": excerpt(text),
                       "story_id": story.get("id"), "story_title": story.get("title"), "story_score": story.get("score") or 0,
                       "story_time": story.get("time"), "comments": comments or 0, "src": src}

n_ch = n_al = 0
for line in open("data/raw/clickhouse_items.jsonl"):
    it = json.loads(line); n_ch += 1
    story = {"id": it.get("story_id"), "title": it.get("story_title"), "score": it.get("story_score"), "time": it.get("story_time")}
    add(it["id"], it["type"], it["by"], it["time"], it.get("text"), it.get("title"), it.get("url"), story, it.get("descendants") if it["type"] != "comment" else 0, src="ch")
for line in open("data/raw/algolia_items.jsonl"):
    h = json.loads(line); n_al += 1
    iid = int(h["objectID"])
    if "comment" in h.get("_tags", []):
        story = {"id": h.get("story_id"), "title": h.get("story_title"), "score": None, "time": None}
        add(iid, "comment", h.get("author"), h["created_at_i"], h.get("comment_text"), None, None, story)
    else:
        story = {"id": iid, "title": h.get("title"), "score": h.get("points"), "time": h["created_at_i"]}
        add(iid, "story", h.get("author"), h["created_at_i"], h.get("story_text"), h.get("title"), h.get("url"), story, h.get("num_comments"))

for m in mentions.values():                          # a submission is its own thread
    if m["type"] != "comment": m["story_comments"] = m.get("comments") or 0
# thread points / comment counts from pipeline/fetch_threads.py (Algolia comments carry neither)
DUMP_TIME = 1692316811                               # the ClickHouse dump ends 2023-08-18
ALG_TIME = os.path.getmtime("data/raw/algolia_items.jsonl") if os.path.exists("data/raw/algolia_items.jsonl") else 0
if os.path.exists("data/cache/threads.json"):
    th = json.load(open("data/cache/threads.json"))
    for m in mentions.values():
        t = th.get(str(m["story_id"]))
        if not t: continue
        obs = DUMP_TIME if m.get("src") == "ch" else ALG_TIME              # when the item's own numbers were observed
        fresh = t.get("fetched_at", 0) >= obs                                 # the newer observation wins, even if it is lower
        if fresh or not m["story_score"]: m["story_score"] = t["score"]
        if fresh or not m.get("story_comments"): m["story_comments"] = t["descendants"]
        if t.get("title") and not m["story_title"]: m["story_title"] = t["title"]
        if m["type"] != "comment": m["comments"] = m["story_comments"]
with open("data/mentions.jsonl", "w") as f:
    for m in mentions.values(): f.write(json.dumps(m) + "\n")
apps = {m["app_key"] for m in mentions.values()}
print(f"raw items: clickhouse {n_ch}, algolia {n_al}; mentions {len(mentions)}; apps {len(apps)} "
      f"(ios {sum(a.startswith('ios:') for a in apps)}, android {sum(a.startswith('android:') for a in apps)})", file=sys.stderr)
