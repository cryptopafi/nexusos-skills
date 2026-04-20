---
name: cortex-knowledge-base
description: "Search and store knowledge in Cortex (team KB)."
---

Search and store knowledge in Cortex (team KB). Use for procedures, rules, decisions, research.

# Cortex Knowledge Base

Access: `http://localhost:6400/api/`

## Search
```bash
curl -s http://localhost:6400/api/search -X POST -H "Content-Type: application/json" -d '{"query": "QUERY", "collection": "procedures", "limit": 5}'
```
Collections: `general`, `rules`, `procedures`, `sessions`, `research`, `projects`, `ideas`, `tasks`

## Store
```bash
curl -s http://localhost:6400/api/store -X POST -H "Content-Type: application/json" -d '{"text": "content", "collection": "general", "metadata": {"s
