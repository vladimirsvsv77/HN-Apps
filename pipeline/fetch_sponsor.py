"""Store metadata for the sponsored row (ReelRise). Output: docs/data/sponsor.json"""
import json, requests
from google_play_scraper import app as play_app
import ssl
ssl._create_default_https_context = ssl.create_default_context   # google_play_scraper turns certificate checks off on import: turn them back on

IOS_ID, PKG = "6612022815", "com.reelrise.app"
CONTACT = ""   # email for booking the sponsored row; leave empty to hide the line
ios = requests.get("https://itunes.apple.com/lookup", params={"id": IOS_ID, "country": "us"}, timeout=30).json()["results"][0]
andr = play_app(PKG, lang="en", country="us")
r = [(ios["averageUserRating"], ios["userRatingCount"]), (andr["score"], andr["ratings"])]
r = [(a, b) for a, b in r if a and b]
json.dump({
    "name": "ReelRise", "dev": ios["artistName"], "icon": ios["artworkUrl512"], "cat": ios["primaryGenreName"],
    "tagline": "AI that tells you how to go viral on TikTok, Instagram, YouTube and Facebook",
    "rating": round(sum(a * b for a, b in r) / sum(b for a, b in r), 2) if r else None, "ratings": sum(b for a, b in r),
    "ios": f"https://apps.apple.com/us/app/reelrise-ai-to-go-viral/id{IOS_ID}?pt=127119016&ct=hnapps&mt=8",
    "android": f"https://play.google.com/store/apps/details?id={PKG}&referrer=utm_source%3Dhnapps",
    "site": "https://reelrise.app/?utm_source=hnapps",
    "contact": CONTACT,
}, open("docs/data/sponsor.json", "w"), ensure_ascii=False, indent=1)
print(json.load(open("docs/data/sponsor.json")))
