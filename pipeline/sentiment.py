"""Label every listed mention with sentiment + developer-self-post flag, using the local Claude subscription CLI
(claude -p, Opus 5.5, xhigh). Cached in data/cache/sentiment.json, safe to re-run. Usage: sentiment.py [--test] [--workers N]"""
import json, os, sys, glob, subprocess, time, re, random
from concurrent.futures import ThreadPoolExecutor

CACHE = "data/cache/sentiment_v2.json"   # keyed "<hn item id>:<store key>"
MODEL, EFFORT, BATCH = "claude-opus-5-5", "xhigh", 40
test = "--test" in sys.argv
workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4

PROMPT = """You label Hacker News comments and submissions that link to a mobile app. For EACH item, decide:
- s: the author's stance toward THAT app: "pos" (uses it happily, recommends, praises), "neg" (complains, warns, criticizes, says it got worse, privacy or pricing concerns, prefers an alternative), or "neu" (mentions without judgment: lists it, asks a question, compares neutrally, news, or unclear).
- self: true if the author is the app's developer or team (says "I built", "my app", "we made", announces it, or a Show HN submission of their own app; the username often resembles the developer name), else false. A developer's own post is still labeled s by tone, usually "pos".
Judge only from the text given. Short texts with just a link and no opinion are "neu".
Reply with ONLY a JSON array, one object per item, same order, like [{"k":"<key>","s":"pos","self":false}, ...]. No prose, no code fences.

Items:
"""

os.makedirs("data/cache", exist_ok=True)
def load(): return json.load(open(CACHE)) if os.path.exists(CACHE) else {}
def save(d): json.dump(d, open(CACHE + ".tmp", "w")); os.replace(CACHE + ".tmp", CACHE)

done = load()
items, todo = [], []
for f in sorted(glob.glob("docs/data/app/*.json")):
    a = json.load(open(f))
    for q in a["quotes"]:
        it = {"k": f"{q['id']}:{q['k']}", "app": a["name"], "dev": a["dev"] or "", "by": q["by"] or "", "type": "submission" if q["type"] != "comment" else "comment",
              "title": (q.get("title") or "")[:150], "text": (q["text"] or "")[:700]}
        items.append(it)
        if not any(f"{q['id']}:{k}" in done for k in a["keys"]): todo.append(it)
random.seed(7); random.shuffle(todo)
if test: todo = todo[:BATCH]
batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
print(f"{len(items)} mentions, {len(done)} cached, {len(todo)} to do in {len(batches)} batches (workers={workers})", file=sys.stderr)

def run_batch(batch):
    got, pending = {}, list(batch)
    for attempt in range(3):                          # retry only the items that came back missing or malformed
        prompt = PROMPT + "\n".join(json.dumps({k: v for k, v in it.items() if v != ""}, ensure_ascii=False) for it in pending)
        try:
            r = subprocess.run(["claude", "-p", "--model", MODEL, "--effort", EFFORT, "--tools", ""], input=prompt, capture_output=True, text=True, timeout=1200)
            m = re.search(r"\[.*\]", r.stdout, re.S)
            arr = json.loads(m.group(0)) if m else []
            want = {b["k"] for b in pending}
            for x in arr if isinstance(arr, list) else []:
                if not isinstance(x, dict) or x.get("k") not in want or x.get("s") not in ("pos", "neg", "neu"): continue
                sf = x.get("self")
                if isinstance(sf, str) and sf.lower() in ("true", "false"): sf = sf.lower() == "true"
                if not isinstance(sf, bool): continue
                got[x["k"]] = {"s": x["s"], "self": sf}
            pending = [b for b in pending if b["k"] not in got]
            if not pending: return got
            print(f"attempt {attempt}: {len(pending)} of {len(batch)} still unlabeled", file=sys.stderr)
        except Exception as e:
            print(f"error (attempt {attempt}): {e}", file=sys.stderr)
        time.sleep(20 * (attempt + 1))
    return got

n = 0; t0 = time.time()
with ThreadPoolExecutor(max_workers=workers) as ex:
    for res in ex.map(run_batch, batches):
        done.update(res); n += 1; save(done)
        print(f"batch {n}/{len(batches)} +{len(res)} labels, total {len(done)}, {int(time.time() - t0)}s", file=sys.stderr)
missing = [it["k"] for it in todo if it["k"] not in done]
if missing:
    print(f"ERROR: {len(missing)} mentions still have no label after retries, e.g. {missing[:3]}. Re-run before publishing.", file=sys.stderr)
from collections import Counter
print("done:", Counter(v["s"] for v in done.values()), "self:", sum(v["self"] for v in done.values()), file=sys.stderr)
if missing: sys.exit(1)
