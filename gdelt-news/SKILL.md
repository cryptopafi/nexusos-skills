---
name: gdelt-news
description: "Real-time news search via GDELT Event Database"
---

Real-time news search via GDELT Event Database

# GDELT Global News Search

## When to Use
Breaking news, global events, trend detection, news monitoring for any topic.

## API
```bash
curl -s "https://api.gdeltproject.org/api/v2/doc/doc?query=QUERY&mode=ArtList&format=json&maxrecords=50&sort=DateDesc"
```

## Parameters
- query: URL-encoded search terms (e.g., "solar%20romania", "panouri%20solare")
- maxrecords: 10-250 (default 50)
- sort: DateDesc (newest first) or DateAsc

## Response Format
JSON with articles array: each has url, title, s
