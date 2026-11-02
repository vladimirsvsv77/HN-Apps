# HN Apps dataset

Every link to an App Store or Google Play page in a Hacker News comment or submission, 2008 to today, with a sentiment label on every mention of an app that is still on a store. Built for people and for agents: plain JSON, no API, no key.

License: CC BY 4.0 for the labels and the derived tables. The comment text itself is Hacker News content, available through the public HN API, and belongs to its authors. Store names, descriptions, icons, screenshots and ratings belong to the developers and the stores, and are not covered by CC BY.

## Files

| File | What it is |
|---|---|
| `mentions.jsonl` (`.gz`) | One row per HN item and app: the mention, the thread it sits in, and its label. 24,626 rows, 4.9 MB gzipped. |
| `apps.json` | The 6,552 apps still on a store, with the compact fields the list page uses, sorted by HN score. |
| `app/<slug>.json` | One file per app: store metadata, stats, and every HN mention with its label. |
| `stats.json` | The aggregates behind the Insights page. |
| `sponsor.json` | The sponsored row. Not data. |

## The unit: a mention

A mention is one HN item (comment or submission) linking one app. When an item links both the iOS and the Android listing of the same app, that is one mention. Every count on the site, in `stats.json` and in this file uses that unit.

The iOS and Android listings of an app are treated as one app when they come from the same developer and have matching names, or when someone linked both in the same HN post and their names or developer match. Merges and slugs are remembered in `pipeline/identity.json` so they stay stable across rebuilds. Apps that are no longer on either store stay in `mentions.jsonl` with `listed: false` and are not on the site.

## `mentions.jsonl` fields

| Field | Type | Meaning |
|---|---|---|
| `item_id` | int | HN item id: `https://news.ycombinator.com/item?id=<item_id>` |
| `type` | `comment` or `submission` | |
| `by` | string | HN username |
| `time` | int | Unix seconds |
| `app` | string or null | Slug of the app on the site, null when it is no longer on a store |
| `listed` | bool | Whether the app is on the site |
| `store_keys` | list | The store listings that make up the app, like `ios:1464477788` or `android:com.pranapps.hack` |
| `store`, `store_id`, `store_url` | | The store link as it appeared in this item |
| `title` | string or null | Submission title (submissions only) |
| `text` | string | Plain text of the comment or submission, first 1,500 characters |
| `story_id`, `story_title` | | The thread the mention is in (the item itself for submissions) |
| `thread_points`, `thread_comments` | int | Points and comment count of that thread. For a comment these describe the thread, not the comment: comment votes are not public |
| `sentiment` | `pos`, `neu`, `neg` or null | The author's stance toward the app. Null when the app is not listed |
| `by_developer` | bool or null | True when the author is the app's developer or team |

## How the labels were made

Each mention of a listed app was labeled by a large language model, given the app name, developer, username, and text, with this definition: `pos` means the author uses, recommends or praises the app; `neg` means they complain, warn, criticize, or prefer an alternative; `neu` means a mention without judgment. `by_developer` is set when the author says they built it or the post is their own launch, and for every mention by a user who is the developer elsewhere.

An app gets a mood on the site when at least three people other than the developer take a side and the mentions lean clearly one way: (positive minus negative) is at least 40% of the labeled mentions by other people, either way.

The labels are good, not perfect. The model sees the text, not the thread, so irony and quoted replies can fool it. The thread is always one click away.

## Counts at export

- 24,626 mentions, 10,704 of them on listed apps
- Labels on listed apps: 7,000 positive, 3,289 neutral, 415 negative
- 4,927 mentions of listed apps (46%) are by the app's own developer

## The score

A comment adds 1. A submission adds 1 + log2(points + 1) + log2(comments + 1). Each distinct HN user who mentioned the app adds 1. The developer's own posts add only the log terms, the reaction other people gave them, and the developer does not count as a user. The logs keep one viral launch from outranking an app that thirty people bring up on their own.

## Sources

HN data from the public HN dump (via the ClickHouse playground, through August 2023) and the Algolia HN API after that, with thread points and comment counts from the HN Firebase API. Store metadata from the iTunes Lookup API and Google Play.
