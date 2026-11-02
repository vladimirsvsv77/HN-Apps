"""Render the 1200x630 link-preview image (docs/og.png) with headless Chrome. Re-run after a rebuild if the top apps change."""
import json, os, subprocess, tempfile, html

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
db = json.load(open("docs/data/apps.json"))
apps = [a for a in db["apps"] if a.get("i")][:7]
n_apps, n_mentions, since = len(db["apps"]), db["listed_mentions"], db["since"]
icons = "".join(f'<div class="app"><img src="{html.escape(a["i"])}"><span class="r">{i+1}</span></div>' for i, a in enumerate(apps))
page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0}}
body{{width:1200px;height:630px;background:#f6f6ef;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display",system-ui,sans-serif;color:#1a1a1a;-webkit-font-smoothing:antialiased;overflow:hidden}}
.bar{{height:84px;background:#ff6600;display:flex;align-items:center;gap:18px;padding:0 64px}}
.mk{{width:40px;height:40px;border:3px solid #fff;color:#fff;font-weight:800;font-size:26px;display:grid;place-items:center;padding-bottom:2px}}
.nm{{font-weight:700;font-size:32px;letter-spacing:-.01em}}
.main{{height:546px;padding:0 64px;display:flex;flex-direction:column;justify-content:center}}
h1{{font-size:68px;line-height:1.04;letter-spacing:-.03em;font-weight:700;max-width:900px}}
p{{font-size:28px;color:#6b6b6b;margin-top:18px;letter-spacing:-.005em}}
p b{{color:#0a7cff;font-weight:600}}
.row{{display:flex;gap:30px;margin-top:56px}}
.app{{display:flex;flex-direction:column;align-items:center;gap:14px}}
.app img{{width:124px;height:124px;border-radius:28px;box-shadow:0 0 0 1px rgba(0,0,0,.08),0 8px 22px rgba(0,0,0,.09);object-fit:cover;background:#fff}}
.r{{font-size:20px;font-weight:600;color:#9a9a93;font-variant-numeric:tabular-nums}}
</style></head><body>
<div class="bar"><span class="mk">A</span><span class="nm">HN Apps</span></div>
<div class="main"><h1>Apps Hacker News talks about</h1>
<p><b>{n_apps:,}</b> iOS and Android apps · <b>{n_mentions/1000:.1f}K</b> HN mentions · since {since}</p>
<div class="row">{icons}</div></div></body></html>"""
with tempfile.TemporaryDirectory() as d:
    src = os.path.join(d, "og.html"); open(src, "w").write(page)
    out = os.path.abspath("docs/og.png")
    subprocess.run([CHROME, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1", "--window-size=1200,630",
                    "--virtual-time-budget=8000", "--default-background-color=f6f6efff", f"--screenshot={out}", "file://" + src],
                   check=True, capture_output=True, timeout=120)
print("wrote", out, os.path.getsize(out) // 1024, "KB")
