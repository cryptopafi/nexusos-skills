---
name: reddit-search
description: "Reddit community search via JSON API (no auth)"
---

Reddit community search via JSON API (no auth)

# Reddit Search (via JSON API)

## When to Use
Community sentiment, product discussions, tech trends, Romanian community opinions.

## API (no auth needed for read-only)
```bash
curl -s -H "User-Agent: genie-research/1.0" "https://www.reddit.com/r/Romania/search.json?q=QUERY&sort=new&limit=25&t=month"
```

## Key Subreddits
- r/Romania — Romanian community, politics, economy
- r/solar — Solar energy community
- r/startups — Startup advice and news
- r/technology — Tech trends
- r/ArtificialIntel
