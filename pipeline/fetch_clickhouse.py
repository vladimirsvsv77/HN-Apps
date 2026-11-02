"""Pull every HN item (through Aug 2023) whose text/url has an App Store or Play link, plus the root story for each comment."""
import json, os, sys, time
import requests

CH = "https://play.clickhouse.com/?user=play"
os.makedirs("data/raw", exist_ok=True)
OUT = "data/raw/clickhouse_items.jsonl"
PATTERNS = ["apps.apple.com", "itunes.apple.com", "play.google.com", "market.android.com", "market://details", "market:&#x2F;&#x2F;details"]   # bare domains: HN escapes "/" as &#x2F; in text

def ch(sql, retries=4):
    for i in range(retries):
        r = requests.post(CH, data=sql.encode(), timeout=180)
        if r.ok:
            return r.text
        print("CH error", r.status_code, r.text[:200], file=sys.stderr)
        time.sleep(5 * (i + 1))
    raise RuntimeError("clickhouse failed")

def rows(sql):
    return [json.loads(l) for l in ch(sql + " FORMAT JSONEachRow").splitlines() if l.strip()]

cond = " OR ".join(f"positionCaseInsensitive(text,'{p}')>0 OR positionCaseInsensitive(url,'{p}')>0" for p in PATTERNS)
items = rows(f"""
SELECT id, type, by, toUnixTimestamp(time) AS time, text, url, title, parent, score, descendants, deleted, dead
FROM hackernews WHERE ({cond}) AND deleted=0 AND dead=0
""")
print("matched items", len(items), file=sys.stderr)

# resolve root story for comments by walking parent chain
by_id = {it["id"]: it for it in items}
need = {it["parent"] for it in items if it["type"] == "comment"}
known = {}  # id -> {type,parent,title,score,time,by}
root_of = {}
pending = set(need)
rounds = 0
while pending and rounds < 40:
    rounds += 1
    batch = list(pending)[:5000]
    pending -= set(batch)
    got = rows(f"SELECT id, type, parent, title, score, toUnixTimestamp(time) AS time, by FROM hackernews WHERE id IN ({','.join(map(str, batch))})")
    for g in got:
        known[g["id"]] = g
        if g["type"] not in ("story", "poll") and g["parent"] and g["parent"] not in known:
            pending.add(g["parent"])
    print(f"round {rounds}: fetched {len(got)}, pending {len(pending)}", file=sys.stderr)

def root(pid, depth=0):
    while pid in known and depth < 100:
        k = known[pid]
        if k["type"] in ("story", "poll"):
            return k
        pid = k["parent"]; depth += 1
    return None

with open(OUT, "w") as f:
    for it in items:
        rec = dict(it)
        if it["type"] == "comment":
            r = root(it["parent"])
            if r:
                rec["story_id"] = r["id"]; rec["story_title"] = r["title"]; rec["story_score"] = r["score"]; rec["story_time"] = r["time"]
        else:
            rec["story_id"] = it["id"]; rec["story_title"] = it["title"]; rec["story_score"] = it["score"]; rec["story_time"] = it["time"]
        f.write(json.dumps(rec) + "\n")
print("wrote", OUT, file=sys.stderr)
