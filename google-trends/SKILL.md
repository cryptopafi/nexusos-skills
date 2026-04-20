---
name: google-trends
description: "Google Trends data via pytrends library"
---

Google Trends data via pytrends library

# Google Trends Analysis

## When to Use
Trend detection, seasonal patterns, keyword interest comparison, Romania-specific search trends.

## Method
Uses pytrends Python library (unofficial Google Trends API).

## Script
```bash
python3 ~/.openclaw/scripts/trends-query.py "keyword1,keyword2" --geo RO --timeframe "today 3-m"
```

## Parameters
- keywords: comma-separated (max 5)
- geo: RO (Romania), or empty for global
- timeframe: "today 3-m" (3 months), "today 12-m" (1 year), "2024-01-01 2026-0
