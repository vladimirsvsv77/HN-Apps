"""Refresh the numbers in README.md and docs/data/DATA.md from the current build, so the docs never drift from the data."""
import json, os, re

s = json.load(open("docs/data/stats.json")); d = json.load(open("docs/data/apps.json"))
sh = s["show_hn"]; Y = s["years"]; li = Y.index(s["partial_year"] - 1); l3 = li - 3
mo = sh["monthly"]; i = mo["months"].index("2022-11"); pre = sum(mo["launches"][i - 12:i]) / 12; last = sum(mo["launches"][-12:]) / 12
ai = [a / f * 100 if f else 0 for a, f in zip(s["ai_first_seen"], s["first_seen"])]
bm = max((b["hit10"], k) for k, b in enumerate(sh["by_month"]) if b["n"] >= 100)
bd = max((b["hit10"], k) for k, b in enumerate(sh["by_weekday"]))
cp = sorted(s["category_points"], key=lambda c: -c["hit10"])
rows = [json.loads(l) for l in open("docs/data/mentions.jsonl")]; listed = [r for r in rows if r["listed"]]
lab = {k: sum(r["sentiment"] == k for r in listed) for k in ("pos", "neu", "neg")}; dev = sum(bool(r["by_developer"]) for r in listed)
gz = os.path.getsize("docs/data/mentions.jsonl.gz") / 1024 / 1024
M = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
D = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
H = lambda h: "noon" if h == 12 else "midnight" if h in (0, 24) else f"{h % 12}{'am' if h < 12 else 'pm'}"
win = sh["best_window"]; devpct = round(dev / len(listed) * 100)
pts_word = "fewer" if sh["by_year"][li]["mean"] < sh["by_year"][l3]["mean"] else "more"

SG = s["significance"]
pf = lambda p: "p < 0.001" if p < 0.001 else f"p = {p:.3f}" if p < 0.01 else f"p = {p:.2f}"
pct = lambda h, n: round(h / n * 100)
wk, mo_, hr, ct = SG["weekday"], SG["month"], SG["hour"], SG["category"]
parts = []
for g, label, names in ((wk, "day of week", D), (mo_, "month", M), (hr, "hour", [H(h) for h in range(24)])):
    parts.append((g["p"] < 0.05, label, names[g["best"]], g, ))
real = [x for x in parts if x[0]]; noise = [x for x in parts if not x[0]]
timing_line = (f"- {round(sh['all_hit10'] * 100)}% of Show HN app launches reach 10 points, and launch timing matters less than people think. "
               + " ".join(f"The {lbl} does make a difference ({pf(g['p'])}): {name} launches reach 10 points {pct(g['best_hits'], g['best_n'])}% of the time, against {pct(g['rest_hits'], g['rest_n'])}% otherwise." for _, lbl, name, g in real)
               + (" " + " and ".join(f"{lbl} ({pf(g['p'])})" for _, lbl, name, g in noise).capitalize() + " differences are within chance." if noise else "")
               + " <!--timing-->\n")
cbest = s["category_points"][ct["best"]]
category_line = (f"- {cbest['name']} launches reach 10 points most often, {pct(ct['best_hits'], ct['best_n'])}% of {ct['best_n']} ({pf(ct['p'])} across categories). <!--category-->\n" if ct["p"] < 0.05 else
                 f"- No store category clearly does better: {cbest['name']} looks best at {pct(ct['best_hits'], ct['best_n'])}% of {ct['best_n']} launches, but the differences are within chance ({pf(ct['p'])}). <!--category-->\n")
r = open("README.md").read()
subs = [
    (r"\*\*[\d,]+ apps · [\d,]+ mentions", f"**{len(d['apps']):,} apps · {len(rows):,} mentions"),
    (r"what [\d,]+ Show HN app launches", f"what {sh['total']:,} Show HN app launches"),
    (r"run at \*\*[\d.]+x the pace", f"run at **{last / pre:.1f}x the pace"),
    (r"each one earns (?:fewer|more) points: [\d.]+ on average in \d{4}, [\d.]+ in \d{4}\.", f"each one earns {pts_word} points: {sh['by_year'][li]['mean']} on average in {Y[li]}, {sh['by_year'][l3]['mean']} in {Y[l3]}."),
    (r"\*\*\d+% of apps first linked in \d{4} have \"AI\" in the name\*\*, (?:up|down) from \d+% in \d{4}\.", f"**{round(ai[li])}% of apps first linked in {Y[li]} have \"AI\" in the name**, {'up' if ai[li] >= ai[l3] else 'down'} from {round(ai[l3])}% in {Y[l3]}."),
    (r"- .*<!--timing-->\n", timing_line),
    (r"- .*<!--category-->\n", category_line),
    (r"- \d+% of the mentions of apps still on a store", f"- {devpct}% of the mentions of apps still on a store"),
    (r"[\d,]+ rows, [\d.]+ MB gzipped", f"{len(rows):,} rows, {gz:.1f} MB gzipped"),
]
t = open("docs/data/DATA.md").read()
subs_t = [
    (r"[\d,]+ rows, [\d.]+ MB gzipped", f"{len(rows):,} rows, {gz:.1f} MB gzipped"),
    (r"The [\d,]+ apps still on a store", f"The {len(d['apps']):,} apps still on a store"),
    (r"- [\d,]+ mentions, [\d,]+ of them on listed apps", f"- {len(rows):,} mentions, {len(listed):,} of them on listed apps"),
    (r"- Labels on listed apps: [\d,]+ positive, [\d,]+ neutral, [\d,]+ negative", f"- Labels on listed apps: {lab['pos']:,} positive, {lab['neu']:,} neutral, {lab['neg']:,} negative"),
    (r"- [\d,]+ mentions of listed apps \(\d+%\)", f"- {dev:,} mentions of listed apps ({devpct}%)"),
]
for pat, rep in subs:
    r, n = re.subn(pat, lambda m: rep, r)
    if n != 1: raise SystemExit(f"README pattern matched {n} times: {pat}")
for pat, rep in subs_t:
    t, n = re.subn(pat, lambda m: rep, t)
    if n != 1: raise SystemExit(f"DATA.md pattern matched {n} times: {pat}")
open("README.md", "w").write(r); open("docs/data/DATA.md", "w").write(t)
print(f"docs updated: {len(d['apps']):,} apps, {len(rows):,} mentions, {len(listed):,} listed")
