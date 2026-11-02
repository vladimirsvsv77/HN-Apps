"""Publish the mentions dataset with sentiment labels. One row per (HN item, app), the same unit every count on the site uses.
Output: docs/data/mentions.jsonl and docs/data/mentions.jsonl.gz"""
import json, gzip, os, collections

ms = {}
for l in open("data/mentions.jsonl"):
    m = json.loads(l); ms[(m["item_id"], m["app_key"])] = m
quotes = {}                                        # (item id, slug) -> the quote the site shows, with its label
for f in os.listdir("docs/data/app"):
    a = json.load(open(os.path.join("docs/data/app", f)))
    for q in a["quotes"]: quotes[(q["id"], a["slug"])] = q
rows = []
for l in open("data/canonical.jsonl"):
    c = json.loads(l); m = ms[(c["item_id"], c["key"])]; q = quotes.get((c["item_id"], c["slug"])) if c["slug"] else None
    rows.append({"item_id": m["item_id"], "type": "comment" if m["type"] == "comment" else "submission", "by": m["by"], "time": m["time"],
                 "app": c["slug"], "listed": bool(c["slug"]), "store_keys": c["keys"], "store": m["store"], "store_id": m["store_id"], "store_url": m["url"],
                 "title": m.get("title"), "text": m.get("text"), "story_id": m["story_id"], "story_title": m["story_title"],
                 "thread_points": m["story_score"] or 0, "thread_comments": m.get("story_comments") or 0,
                 "sentiment": q["s"] if q else None, "by_developer": q["self"] if q else None})
rows.sort(key=lambda r: (r["time"], r["item_id"]))
os.makedirs("docs/data", exist_ok=True)
with open("docs/data/mentions.jsonl", "w") as f, gzip.open("docs/data/mentions.jsonl.gz", "wt") as g:
    for r in rows:
        line = json.dumps(r, ensure_ascii=False) + "\n"; f.write(line); g.write(line)
listed = [r for r in rows if r["listed"]]
c = collections.Counter(r["sentiment"] for r in listed)
print(f"{len(rows)} rows, {len(listed)} on listed apps, labels {dict(c)}, {sum(bool(r['by_developer']) for r in listed)} by developer; "
      f"{os.path.getsize('docs/data/mentions.jsonl')//1024} KB, {os.path.getsize('docs/data/mentions.jsonl.gz')//1024} KB gz")
