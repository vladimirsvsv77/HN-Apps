"""Merge mentions + store metadata into the static site's JSON.
Outputs: docs/data/apps.json, docs/data/app/<slug>.json, docs/data/stats.json, data/app_index.json,
docs/feed.xml, and the link-preview tags in docs/index.html. Set SITE_URL for the public address."""
import json, os, re, math, html, collections, sys, time, statistics
from datetime import datetime
from zoneinfo import ZoneInfo

SITE_URL = os.environ.get("SITE_URL", "https://vladimirsvsv77.github.io/HN-Apps").rstrip("/")
ET = ZoneInfo("America/New_York")
DAY = 86400
NOW = int(time.time())

def load_cache(p, default=None):
    if not os.path.exists(p): return default
    for _ in range(10):
        try: return json.load(open(p))
        except ValueError: time.sleep(1)
    raise RuntimeError(f"cannot read {p}")

mentions = [json.loads(l) for l in open("data/mentions.jsonl")]
IDENT_PATH = "pipeline/identity.json"                # every slug and iOS/Android pair ever published, tracked in git
IDENT = load_cache(IDENT_PATH, {"slugs": {}, "slugs2": {}, "pairs": []}) if os.path.exists(IDENT_PATH) else {"slugs": {}, "slugs2": {}, "pairs": []}
PREV_SLUG, PREV_SLUG2, PREV_PAIRS = dict(IDENT["slugs"]), dict(IDENT["slugs2"]), [tuple(p) for p in IDENT["pairs"]]   # so ids stay stable across rebuilds
if os.path.isdir("docs/data/app"):
    for f in sorted(os.listdir("docs/data/app")):
        try: a = json.load(open(os.path.join("docs/data/app", f)))
        except ValueError: continue
        primary = ("ios:" + a["ios"]["id"]) if a.get("ios") else ("android:" + a["android"]["id"]) if a.get("android") else None
        for k in a.get("keys", []): (PREV_SLUG if k == primary else PREV_SLUG2).setdefault(k, a["slug"])   # the slug belongs to the listing that named the app
        if len(a.get("keys", [])) == 2: PREV_PAIRS.append(tuple(sorted(a["keys"], key=lambda k: not k.startswith("ios:"))))
PREV_PAIRS = sorted(set(PREV_PAIRS))
itunes = load_cache("data/cache/itunes.json", {})
play = load_cache("data/cache/play.json", {})
SENT = load_cache("data/cache/sentiment_v2.json", {})
OVR = load_cache("pipeline/overrides.json", {"merge": [], "split": []})

# ---------------- categories ----------------
CATS = {  # store genre -> site category
    "Productivity": "Productivity", "Utilities": "Utilities", "Tools": "Utilities", "Developer Tools": "Developer Tools",
    "Social Networking": "Social", "Social": "Social", "Communication": "Communication", "Photo & Video": "Photo & Video",
    "Photography": "Photo & Video", "Video Players & Editors": "Photo & Video", "Music": "Music & Audio", "Music & Audio": "Music & Audio",
    "Health & Fitness": "Health & Fitness", "Medical": "Health & Fitness", "Finance": "Finance", "Education": "Education",
    "Games": "Games", "News": "News & Reading", "News & Magazines": "News & Reading", "Books": "News & Reading",
    "Books & Reference": "News & Reading", "Reference": "News & Reading", "Magazines & Newspapers": "News & Reading", "Comics": "News & Reading",
    "Newsstand": "News & Reading", "Travel": "Travel & Maps", "Travel & Local": "Travel & Maps", "Navigation": "Travel & Maps",
    "Maps & Navigation": "Travel & Maps", "Shopping": "Shopping & Food", "Food & Drink": "Shopping & Food", "Lifestyle": "Lifestyle",
    "Entertainment": "Entertainment", "Business": "Business", "Weather": "Weather", "Sports": "Sports", "Art & Design": "Art & Design",
    "Graphics & Design": "Art & Design", "Personalization": "Utilities", "Libraries & Demo": "Developer Tools", "Auto & Vehicles": "Lifestyle",
    "House & Home": "Lifestyle", "Parenting": "Lifestyle", "Dating": "Social", "Events": "Lifestyle", "Beauty": "Lifestyle", "Kids": "Education",
    "Stickers": "Entertainment", "Health": "Health & Fitness", "Fitness": "Health & Fitness", "Book": "News & Reading",
}
def cat(genre, genre_id=None):
    if genre_id and str(genre_id).startswith("GAME"): return "Games"
    return CATS.get(genre or "", "Other")

# ---------------- name helpers ----------------
STOP = {"the", "a", "an", "and", "for", "app", "apps", "by", "of", "your", "my", "on", "to", "with", "in"}
def toks(s): return {t for t in re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).split() if t not in STOP}
def head(s):
    s = re.split(r"\s+[-–—:|]\s+|\s*[:|]\s+|\s*\(", (s or "").lower(), 1)[0]
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())
def norm_dev(s):
    s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())
    s = re.sub(r"\b(inc|llc|ltd|limited|gmbh|co|corp|corporation|company|the|studio|studios|labs|software|technologies|technology|bv|b v|ab|sa|srl|oy|as|pty|plc)\b", " ", s)
    return " ".join(s.split())
def jacc(a, b): return len(a & b) / len(a | b) if a and b else 0.0
def slug_from_url(u):
    m = re.search(r"/app/([^/]+)/id\d+", u or "")
    return m.group(1).replace("-", " ").title() if m else None
def slugify(s): return (re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60]) or "app"
def chi2_sf(x, k):                                  # P(chi-square with k dof > x), regularized upper gamma, no scipy needed
    a, x2 = k / 2, x / 2
    if x2 <= 0: return 1.0
    if x2 < a + 1:
        t = sm = 1 / a; n = a
        for _ in range(500): n += 1; t *= x2 / n; sm += t
        return max(0.0, 1 - sm * math.exp(-x2 + a * math.log(x2) - math.lgamma(a)))
    b = x2 + 1 - a; c = 1e300; d = 1 / b; h = d
    for i in range(1, 500):
        an = -i * (i - a); b += 2; d = an * d + b; d = 1 / d if d else 1e300; c = b + an / c; h *= d * c
    return h * math.exp(-x2 + a * math.log(x2) - math.lgamma(a))
def sig(groups, min_n=0):                            # groups: list of (hits, n). Chi-square across groups, then best group vs the rest
    gs = [(i, h, n) for i, (h, n) in enumerate(groups) if n >= min_n]
    H, N = sum(h for _, h, _ in gs), sum(n for _, _, n in gs)
    if not N or not H or H == N or len(gs) < 2: return None
    p0 = H / N
    chi = sum((h - n * p0) ** 2 / (n * p0) + ((n - h) - n * (1 - p0)) ** 2 / (n * (1 - p0)) for _, h, n in gs)
    bi, bh, bn = max(gs, key=lambda g: g[1] / g[2]); rh, rn = H - bh, N - bn
    z = (bh / bn - rh / rn) / math.sqrt(p0 * (1 - p0) * (1 / bn + 1 / rn))
    return {"p": round(chi2_sf(chi, len(gs) - 1), 4), "best": bi, "best_hits": bh, "best_n": bn, "rest_hits": rh, "rest_n": rn,
            "p_best": round(math.erfc(abs(z) / math.sqrt(2)), 4)}
def is_show(m): return m["type"] != "comment" and (m.get("title") or "").lower().startswith("show hn")
def et(ts): return datetime.fromtimestamp(ts, ET)

# ---------------- one entity per store listing ----------------
listings = {}
for m in mentions:
    L = listings.setdefault(m["app_key"], {"key": m["app_key"], "store": m["store"], "store_id": m["store_id"], "mentions": [], "urls": collections.Counter()})
    L["mentions"].append(m); L["urls"][m["url"]] += 1
for L in listings.values():
    if L["store"] == "ios":
        meta = itunes.get(L["store_id"])
        if meta and meta.get("kind") != "software": meta = None   # Mac-only or non-app items
        L["meta"] = meta
        L["name"] = (meta or {}).get("trackName") or slug_from_url(L["urls"].most_common(1)[0][0]) or L["store_id"]
        L["dev"] = (meta or {}).get("artistName")
    else:
        meta = play.get(L["store_id"]); L["meta"] = meta
        L["name"] = (meta or {}).get("title") or L["store_id"]
        L["dev"] = (meta or {}).get("developer")

# ---------------- merge iOS + Android listings of the same product (one-to-one) ----------------
item_keys = collections.defaultdict(set)
for m in mentions: item_keys[m["item_id"]].add(m["app_key"])
co = collections.Counter()
for ks in item_keys.values():
    for a in ks:
        if a.startswith("ios:"):
            for b in ks:
                if b.startswith("android:"): co[(a, b)] += 1
alive = {k: L for k, L in listings.items() if L["meta"]}
by_dev, by_head = collections.defaultdict(list), collections.defaultdict(list)
for L in alive.values():
    if norm_dev(L["dev"]): by_dev[norm_dev(L["dev"])].append(L)
    if head(L["name"]): by_head[head(L["name"])].append(L)
df = collections.Counter(t for L in alive.values() for t in toks(L["name"]))
PLATFORM = {"iphone", "ipad", "ios", "android", "mobile", "phone", "tablet", "watch", "mac"}
def generic_diff(A, B):                              # differing words are common ones ("fast", "free", "iPhone"), not two different brand names
    d = toks(A["name"]) ^ toks(B["name"])
    return all(df[t] >= 10 or t in PLATFORM for t in d)
cand = set(k for k in co if k[0] in alive and k[1] in alive)
for grp in list(by_dev.values()) + list(by_head.values()):
    for a in grp:
        for b in grp:
            if a["store"] == "ios" and b["store"] == "android": cand.add((a["key"], b["key"]))
split = {tuple(p) for p in OVR.get("split", [])}
pairs = []
for a, b in cand:
    if (a, b) in split: continue
    A, B = alive[a], alive[b]
    dev_eq = bool(norm_dev(A["dev"])) and norm_dev(A["dev"]) == norm_dev(B["dev"])
    head_eq = bool(head(A["name"])) and head(A["name"]) == head(B["name"])
    j = jacc(toks(A["name"]), toks(B["name"]))
    c = co[(a, b)]
    if (dev_eq and (head_eq or (j >= 0.6 and generic_diff(A, B)))) or (c and (dev_eq or head_eq or (j >= 0.5 and generic_diff(A, B)))):   # franchise collisions go in overrides.json
        pairs.append((c * 10 + j + dev_eq + head_eq, a, b))
partner = {}
for p in OVR.get("merge", []): partner[p[0]] = p[1]; partner[p[1]] = p[0]
for _, a, b in sorted(pairs, reverse=True):
    if a not in partner and b not in partner: partner[a] = b; partner[b] = a
for a, b in PREV_PAIRS:                              # keep an established pair together when one side has left the store
    if a in listings and b in listings and (a, b) not in split and a not in partner and b not in partner and not (a in alive and b in alive):
        partner[a] = b; partner[b] = a
groups, seen = [], set()
for k in sorted(listings):
    if k in seen: continue
    g = [k] + ([partner[k]] if k in partner and partner[k] in listings else [])
    seen.update(g); groups.append(g)

# ---------------- app records ----------------
def ios_block(meta, L):
    return {"id": L["store_id"], "url": meta.get("trackViewUrl") or L["urls"].most_common(1)[0][0], "rating": meta.get("averageUserRating"),
            "ratings": meta.get("userRatingCount"), "price": meta.get("formattedPrice"), "genre": meta.get("primaryGenreName"),
            "screens": (meta.get("screenshotUrls") or meta.get("ipadScreenshotUrls") or [])[:8], "desc": (meta.get("description") or "")[:2500],
            "released": (meta.get("releaseDate") or "")[:10], "updated": (meta.get("currentVersionReleaseDate") or "")[:10],
            "icon": meta.get("artworkUrl512") or meta.get("artworkUrl100"), "age": meta.get("contentAdvisoryRating")}
def android_block(meta, L):
    upd = meta.get("updated")
    return {"id": L["store_id"], "url": f"https://play.google.com/store/apps/details?id={L['store_id']}", "rating": meta.get("score"),
            "ratings": meta.get("ratings"), "price": "Free" if meta.get("free") else (f"${meta.get('price')}" if meta.get("price") else None),
            "installs": meta.get("installs"), "genre": meta.get("genre"), "screens": (meta.get("screenshots") or [])[:8],
            "desc": (meta.get("description") or "")[:2500], "released": meta.get("released"),
            "updated": time.strftime("%Y-%m-%d", time.gmtime(upd)) if isinstance(upd, (int, float)) else None,
            "icon": meta.get("icon"), "age": meta.get("contentRating")}
def label(item, keys):
    for k in keys:
        v = SENT.get(f"{item}:{k}")
        if v: return v
    return None
def weight(m, self_post):
    pts = math.log2(1 + (m["story_score"] or 0)) + math.log2(1 + (m.get("comments") or 0)) if m["type"] != "comment" else 0
    if self_post: return pts                       # a developer's own post counts only for the reaction it got
    return 1 + pts if m["type"] != "comment" else 1.0

canon = []          # every canonical mention: one per (HN item, app group), listed or not
index = {}          # store key -> slug (listed apps only)
apps, used_slugs = [], set()
for keys in groups:
    Ls = [listings[k] for k in keys]
    ms = {}
    for L in Ls:
        for m in L["mentions"]: ms.setdefault(m["item_id"], m)
    ms = list(ms.values())
    ios = next((L for L in Ls if L["store"] == "ios" and L["meta"]), None)
    andr = next((L for L in Ls if L["store"] == "android" and L["meta"]), None)
    listed = bool(ios or andr)
    for m in ms: canon.append({"m": m, "keys": keys, "listed": listed})
    if not listed: continue
    primary = ios or andr
    rec = {"name": primary["name"], "dev": primary["dev"], "keys": keys,
           "ios": ios_block(ios["meta"], ios) if ios else None, "android": android_block(andr["meta"], andr) if andr else None}
    rec["icon"] = (rec["ios"] or rec["android"] or {}).get("icon")
    rec["cat"] = cat(ios["meta"].get("primaryGenreName") if ios else andr["meta"].get("genre"), None if ios else andr["meta"].get("genreId"))
    rs = [b for b in (rec["ios"], rec["android"]) if b and b.get("rating") and b.get("ratings")]
    rec["rating"] = round(sum(b["rating"] * b["ratings"] for b in rs) / sum(b["ratings"] for b in rs), 2) if rs else None
    rec["ratings"] = sum(b["ratings"] for b in rs) if rs else 0
    labs = {m["item_id"]: label(m["item_id"], keys) for m in ms}
    dev_users = {m["by"] for m in ms if labs[m["item_id"]] and labs[m["item_id"]]["self"] and m["by"]}
    def is_self(m): return bool(labs[m["item_id"]] and labs[m["item_id"]]["self"]) or (m["by"] in dev_users)
    outside = {m["by"] for m in ms if m["by"] and not is_self(m)}
    users = {m["by"] for m in ms if m["by"]}
    subs = [m for m in ms if m["type"] != "comment"]
    show = sorted([m for m in ms if is_show(m)], key=lambda m: -(m["story_score"] or 0))
    pos = neg = n = 0; sided = set()
    for m in ms:
        lab = labs[m["item_id"]]
        if not lab or is_self(m): continue
        n += 1; pos += lab["s"] == "pos"; neg += lab["s"] == "neg"
        if lab["s"] in ("pos", "neg") and m["by"]: sided.add(m["by"])
    s_ = (pos - neg) / n if n else 0
    mood = ("up" if s_ >= 0.4 else "down" if s_ <= -0.4 else None) if len(sided) >= 3 else None
    rec.update({"mentions": len(ms), "users": len(users), "threads": len({m["story_id"] for m in ms if m["story_id"]}),
                "hn_points": sum((m["story_score"] or 0) for m in subs), "hn_comments": sum((m.get("comments") or 0) for m in subs),
                "submissions": len(subs), "self_n": sum(is_self(m) for m in ms),
                "hn_score": round(sum(weight(m, is_self(m)) for m in ms) + len(outside), 2),
                "first": min(m["time"] for m in ms), "last": max(m["time"] for m in ms),
                "show_hn": {"time": show[0]["time"], "points": show[0]["story_score"] or 0, "id": show[0]["item_id"], "title": show[0]["title"]} if show else None,
                "n_lab": n, "pos_pct": round(pos / n * 100) if n else None, "neg_pct": round(neg / n * 100) if n else None, "mood": mood})
    uid = {u: i for i, u in enumerate(sorted(outside))}
    rec["quotes"] = sorted([{"id": m["item_id"], "k": m["app_key"], "type": m["type"], "by": m["by"], "time": m["time"], "text": m["text"] or "",
                             "title": m.get("title"), "story_id": m["story_id"], "story_title": m["story_title"],
                             "story_score": m["story_score"] or 0, "comments": m.get("comments") or 0,
                             "w": round(weight(m, is_self(m)), 3), "u": -1 if is_self(m) else uid.get(m["by"], -1),
                             "s": labs[m["item_id"]]["s"] if labs[m["item_id"]] else None, "self": is_self(m)} for m in ms],
                           key=lambda q: (-q["story_score"], -q["time"]))
    prim_key = ios["key"] if ios else andr["key"]
    shared = {PREV_SLUG.get(k) or PREV_SLUG2.get(k) for k in keys}         # the slug the whole group had last time
    rec["_prev"], rec["_prev_rank"] = (shared.pop(), -1) if len(keys) == 2 and len(shared) == 1 and None not in shared else \
        (PREV_SLUG[prim_key], 0) if prim_key in PREV_SLUG else \
        next(((PREV_SLUG[k], 1) for k in keys if k in PREV_SLUG), None) or next(((PREV_SLUG2[k], 2) for k in keys if k in PREV_SLUG2), (None, 3))
    apps.append(rec)
historic = set(IDENT["slugs"].values()) | set(IDENT["slugs2"].values())   # every slug ever published stays with its owner
for rec in sorted(apps, key=lambda r: (r["_prev_rank"], r["keys"][0])):
    sl = rec.pop("_prev"); rec.pop("_prev_rank")
    if not sl or sl in used_slugs:
        base = slugify(rec["name"]); sl, i = base, 2
        while sl in used_slugs or sl in historic: sl = f"{base}-{i}"; i += 1
    used_slugs.add(sl); rec["slug"] = sl
    for k in rec["keys"]: index[k] = sl

apps.sort(key=lambda a: (-a["hn_score"], -a["mentions"], -a["users"], a["slug"]))
os.makedirs("docs/data/app", exist_ok=True); os.makedirs("data", exist_ok=True)
for f in os.listdir("docs/data/app"): os.remove(os.path.join("docs/data/app", f))
for a in apps: json.dump(a, open(f"docs/data/app/{a['slug']}.json", "w"), ensure_ascii=False, separators=(",", ":"))
json.dump(index, open("data/app_index.json", "w"))
pairs_now = {tuple(sorted(g, key=lambda k: not k.startswith("ios:"))) for g in groups if len(g) == 2}
IDENT["pairs"] = sorted(pairs_now | {p for p in PREV_PAIRS if p[0] in listings and p[1] in listings and tuple(p) not in split
                                        and not (p[0] in alive and p[1] in alive)})   # a pair re-checked and rejected today is forgotten
for a in apps:
    prim = ("ios:" + a["ios"]["id"]) if a["ios"] else ("android:" + a["android"]["id"])
    for k in a["keys"]:
        (IDENT["slugs"] if k == prim else IDENT["slugs2"])[k] = a["slug"]
        (IDENT["slugs2"] if k == prim else IDENT["slugs"]).pop(k, None)   # a key's latest role wins, so a merged app keeps its slug
json.dump(IDENT, open(IDENT_PATH + ".tmp", "w"), indent=0, sort_keys=True); os.replace(IDENT_PATH + ".tmp", IDENT_PATH)
with open("data/canonical.jsonl", "w") as f:       # one row per (HN item, app): the unit every count on the site uses
    for c in canon: f.write(json.dumps({"item_id": c["m"]["item_id"], "key": c["m"]["app_key"], "keys": c["keys"], "slug": index.get(c["keys"][0])}) + "\n")

n_canon, n_listed = len(canon), sum(c["listed"] for c in canon)
first_day = min(q["time"] for a in apps for q in a["quotes"]) // DAY
since_year = et(first_day * DAY).year
def compact(a):
    qs = sorted(a["quotes"], key=lambda q: q["time"])
    return {"s": a["slug"], "n": a["name"], "d": a["dev"], "i": a["icon"], "r": a["rating"], "c": a["ratings"], "g": a["cat"],
            "p": (1 if a["ios"] else 0) | (2 if a["android"] else 0), "m": a["mentions"], "u": a["users"], "h": a["hn_points"],
            "f": a["first"], "l": a["last"], "x": 1 if a["show_hn"] else 0, "k": a["hn_score"],
            "mo": 1 if a["mood"] == "up" else -1 if a["mood"] == "down" else 0, "pp": a["pos_pct"], "pq": a["neg_pct"], "pn": a["n_lab"],
            "t": [q["time"] // DAY for q in qs], "w": [q["w"] for q in qs], "uu": [q["u"] for q in qs],
            "pt": [q["story_score"] if q["type"] != "comment" else 0 for q in qs], "sh": [1 if is_show(q) else 0 for q in qs]}
json.dump({"generated": NOW, "first_day": first_day, "since": since_year, "total_mentions": n_canon, "listed_mentions": n_listed,
           "cats": sorted(collections.Counter(a["cat"] for a in apps).items(), key=lambda x: -x[1]), "apps": [compact(a) for a in apps]},
          open("docs/data/apps.json", "w"), ensure_ascii=False, separators=(",", ":"))
print(f"apps {len(apps)} (ios {sum(1 for a in apps if a['ios'])}, android {sum(1 for a in apps if a['android'])}, both {sum(1 for a in apps if a['ios'] and a['android'])}); "
      f"mentions {n_canon} ({n_listed} listed); up {sum(a['mood']=='up' for a in apps)}, down {sum(a['mood']=='down' for a in apps)}; "
      f"labels missing on listed: {sum(1 for a in apps for q in a['quotes'] if q['s'] is None)}; apps.json {os.path.getsize('docs/data/apps.json')//1024} KB", file=sys.stderr)
other_genres = collections.Counter((a["ios"] or a["android"])["genre"] for a in apps if a["cat"] == "Other")
if other_genres: print("genres mapped to Other:", other_genres.most_common(8), file=sys.stderr)

# ---------------- insights: docs/data/stats.json (US Eastern everywhere) ----------------
this_year = et(NOW).year
stats_since = min(et(c["m"]["time"]).year for c in canon)
years = list(range(stats_since, this_year + 1)); yi = {y: i for i, y in enumerate(years)}
zeros = lambda: [0] * len(years)
sub_y, com_y = zeros(), zeros()
for c in canon:
    y = et(c["m"]["time"]).year
    if y in yi: (sub_y if c["m"]["type"] != "comment" else com_y)[yi[y]] += 1
ios_y, andr_y = zeros(), zeros()
for m in mentions:                                  # store links, not mentions: an item can link both stores
    y = et(m["time"]).year
    if y in yi: (ios_y if m["store"] == "ios" else andr_y)[yi[y]] += 1
AI_RE = re.compile(r"\bAI\b|\bA\.I\.")
first_y, ai_first_y = zeros(), zeros()
cat_y = collections.defaultdict(zeros)
for a in apps:
    y = et(a["first"]).year
    if y in yi:
        first_y[yi[y]] += 1
        if AI_RE.search(a["name"] or ""): ai_first_y[yi[y]] += 1
    for q in a["quotes"]:
        y = et(q["time"]).year
        if y in yi: cat_y[a["cat"]][yi[y]] += 1
top_cats = [c for c in sorted(cat_y, key=lambda c: -sum(cat_y[c])) if c != "Other"][:7]
other = zeros()
for c, v in cat_y.items():
    if c not in top_cats: other = [x + y for x, y in zip(other, v)]
cats_out = [{"name": c, "values": cat_y[c]} for c in top_cats] + [{"name": "Other", "values": other}]

shows = {}
for c in canon:
    if is_show(c["m"]): shows.setdefault(c["m"]["item_id"], c["m"])
def bucket(items):
    pts = [(m["story_score"] or 0) for m in items]
    return {"n": len(pts), "mean": round(statistics.fmean(pts), 1) if pts else 0, "median": statistics.median(pts) if pts else 0,
            "hit10": round(sum(p >= 10 for p in pts) / len(pts), 3) if pts else 0}
full = [m for m in shows.values() if et(m["time"]).year < this_year]          # timing uses complete years only
by_month, by_wday, by_hour = [[] for _ in range(12)], [[] for _ in range(7)], [[] for _ in range(24)]
for m in full:
    d = et(m["time"]); by_month[d.month - 1].append(m); by_wday[d.weekday()].append(m); by_hour[d.hour].append(m)
best_win, best_r = None, -1
for h0 in range(24):                                 # best 4-hour window by share of launches reaching 10 points
    hs = [(h0 + i) % 24 for i in range(4)]; its = [m for h in hs for m in by_hour[h]]
    if len(its) < 300: continue
    r = sum((m["story_score"] or 0) >= 10 for m in its) / len(its)
    if r > best_r: best_r, best_win = r, {"start": h0, "end": (h0 + 4) % 24, "hit10": round(r, 3), "n": len(its)}
all_hit10 = round(sum((m["story_score"] or 0) >= 10 for m in full) / len(full), 3) if full else 0
by_year_show = collections.defaultdict(list)
for m in shows.values(): by_year_show[et(m["time"]).year].append(m)
now_et = et(NOW); months, (y, mo) = [], (2011, 1)
while (y, mo) < (now_et.year, now_et.month):
    months.append(f"{y}-{mo:02d}"); mo += 1
    if mo > 12: y, mo = y + 1, 1
mcount = collections.Counter(et(m["time"]).strftime("%Y-%m") for m in shows.values())
cat_pts = collections.defaultdict(dict)
for a in apps:
    for q in a["quotes"]:
        if q["type"] != "comment" and (q.get("title") or "").lower().startswith("show hn"): cat_pts[a["cat"]][q["id"]] = q["story_score"] or 0
cat_pts = {c: list(v.values()) for c, v in cat_pts.items()}           # one observation per launch post, even if it links two apps
cat_points = sorted([{"name": c, "n": len(v), "mean": round(statistics.fmean(v), 1), "median": statistics.median(v), "hit10": round(sum(p >= 10 for p in v) / len(v), 3)}
                     for c, v in cat_pts.items() if len(v) >= 40 and c != "Other"], key=lambda x: -x["hit10"])
h10 = lambda b: (round(b["hit10"] * b["n"]), b["n"])
SIG = {"weekday": sig([h10(bucket(b)) for b in by_wday]), "month": sig([h10(bucket(b)) for b in by_month]),
       "hour": sig([h10(bucket(b)) for b in by_hour], min_n=120), "category": sig([h10(c) for c in cat_points])}
json.dump({"generated": NOW, "since": stats_since, "list_since": since_year, "years": years, "partial_year": this_year, "tz": "America/New_York",
           "total_mentions": n_canon, "listed_mentions": n_listed, "self_share": round(sum(a["self_n"] for a in apps) / max(1, n_listed), 3),
           "mentions": {"submissions": sub_y, "comments": com_y}, "platform": {"ios": ios_y, "android": andr_y},
           "first_seen": first_y, "ai_first_seen": ai_first_y, "categories": cats_out,
           "show_hn": {"total": len(shows), "by_year": [bucket(by_year_show.get(y, [])) for y in years],
                       "monthly": {"months": months, "launches": [mcount.get(k, 0) for k in months]},
                       "timing_years": [stats_since, this_year - 1], "timing_n": len(full), "all_hit10": all_hit10, "best_window": best_win,
                       "by_month": [bucket(b) for b in by_month], "by_weekday": [bucket(b) for b in by_wday], "by_hour": [bucket(b) for b in by_hour]},
           "category_points": cat_points, "significance": SIG}, open("docs/data/stats.json", "w"))
print(f"stats: {len(shows)} Show HN launches ({len(full)} in complete years), best window {best_win}", file=sys.stderr)

# ---------------- link previews ----------------
desc = (f"{len(apps):,} iOS and Android apps linked in {n_listed:,} Hacker News comments and submissions since {since_year}, "
        f"ranked by HN score, with HN mood per app. Top lists for every week, month and year.")
head_html = f'''<!-- meta:start -->
<link rel="canonical" href="{SITE_URL}/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="HN Apps">
<meta property="og:title" content="HN Apps · Apps Hacker News talks about">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{SITE_URL}/">
<meta property="og:image" content="{SITE_URL}/og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="HN Apps: the top apps Hacker News talks about">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ff6600">
<link rel="alternate" type="application/rss+xml" title="HN Apps · top apps of the week" href="feed.xml">
<!-- meta:end -->'''
idx = open("docs/index.html").read()
idx = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{html.escape(desc)}">', idx)
if "<!-- meta:start -->" in idx: idx = re.sub(r"<!-- meta:start -->.*?<!-- meta:end -->", lambda m: head_html, idx, flags=re.S)
else: idx = idx.replace('<link rel="stylesheet" href="style.css">', head_html + '\n<link rel="stylesheet" href="style.css">')
open("docs/index.html", "w").write(idx)

# ---------------- weekly RSS: same score as the site's week view ----------------
from xml.sax.saxutils import escape as xesc
from email.utils import formatdate
def wk_start(d): return d - ((d + 3) % 7)          # Monday-start weeks in UTC days, as on the site
def day_label(d): t = time.gmtime(d * DAY); return f"{time.strftime('%b', t)} {t.tm_mday}"
cur = wk_start(NOW // DAY)
items = []
for ws in [cur - 7 * k for k in range(1, 13)]:
    we = ws + 7; scored = []
    for a in apps:
        qs = [q for q in a["quotes"] if ws <= q["time"] // DAY < we]
        if not qs: continue
        k = sum(q["w"] for q in qs) + len({q["u"] for q in qs if q["u"] >= 0})
        scored.append((k, len(qs), a, any(is_show(q) for q in qs)))
    if not scored: continue
    scored.sort(key=lambda x: (-x[0], -x[1], -x[2]["hn_score"], x[2]["slug"]))
    key = time.strftime("%Y-%m-%d", time.gmtime(ws * DAY))
    label_ = f"{day_label(ws)} – {day_label(we - 1)}, {time.gmtime((we - 1) * DAY).tm_year}"
    li = "".join(f'<li><a href="{SITE_URL}/#/app/{a["slug"]}">{html.escape(a["name"])}</a>, {n} mention{"s" if n != 1 else ""}{" · Show HN" if sh else ""}</li>'
                 for k, n, a, sh in scored[:10])
    body = (f'<p>{len(scored)} app{"s" if len(scored) != 1 else ""} {"were" if len(scored) != 1 else "was"} linked on Hacker News this week. '
            f'The top {min(10, len(scored))}:</p><ol>{li}</ol><p><a href="{SITE_URL}/#/top/week/{key}">Full list</a></p>')
    items.append(f'''  <item>
    <title>Top apps on HN, {xesc(label_)}</title>
    <link>{SITE_URL}/#/top/week/{key}</link>
    <guid isPermaLink="false">hnapps-week-{key}</guid>
    <pubDate>{formatdate(we * DAY, usegmt=True)}</pubDate>
    <description>{xesc(body)}</description>
  </item>''')
open("docs/feed.xml", "w").write(f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>HN Apps · top apps of the week</title>
  <link>{SITE_URL}/</link>
  <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
  <description>The iOS and Android apps Hacker News linked most each week.</description>
  <language>en</language>
  <lastBuildDate>{formatdate(NOW, usegmt=True)}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
''')
print(f"meta + feed: {SITE_URL}, {len(items)} weekly items", file=sys.stderr)
