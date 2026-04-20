---
name: hackernews-search
description: "Hacker News search via Algolia API"
---

Hacker News search via Algolia API

# HackerNews Search (Algolia API)

## When to Use
Tech trends, developer sentiment, startup intelligence, AI news.

## API
```bash
curl -s "https://hn.algolia.com/api/v1/search?query=QUERY&tags=story&hitsPerPage=20"
```

## Parameters
- query: search terms
- tags: story (posts only), comment (comments only)
- hitsPerPage: 1-100
- numericFilters: created_at_i>UNIX_TIMESTAMP (filter by date)

## Response Format
JSON with hits array: each has title, url, points, num_comments, created_at, objectID


