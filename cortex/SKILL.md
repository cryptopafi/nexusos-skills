---
name: cortex
description: Search, store, and retrieve from the NexusOS Cortex knowledge base using the REST API.
metadata:
  openclaw:
    emoji: "\U0001F9E0"
    requires:
      bins:
        - curl
        - jq
---

# Cortex Skill

Use this skill to interact with the NexusOS Cortex knowledge base.

## Setup

Get the Cortex base URL (run once per session):
```bash
CORTEX_URL=$(jq -r '.cortex_url // "http://localhost:6400"' ~/.nexus/config/cortex.json 2>/dev/null || echo "http://localhost:6400")
```

## cortex_health — Check Cortex is running

```bash
curl -sf "$CORTEX_URL/api/health" | jq .
```

Returns `{"ok": true, "version": "..."}` if healthy. If this fails, Cortex is down. Report to user.

## cortex_search — Search knowledge base

```bash
curl -sf -X POST "$CORTEX_URL/api/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "<QUERY>", "limit": 5}' | jq .
```

Optional: add `"collection": "<NAME>"` to scope results. Collections: `procedures`, `intelligence`, `technical`, `business`, `training_procedures`.

Returns:
```json
{"results": [{"title": "...", "text": "...", "score": 0.85, "metadata": {...}}]}
```

## cortex_find_procedure — Find a specific procedure

```bash
curl -sf -X POST "$CORTEX_URL/api/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "<KEYWORD_OR_RULE_ID>", "collection": "procedures", "limit": 3}' | jq .
```

## cortex_store — Store a new item

For non-procedure collections (intelligence, technical, business):
```bash
curl -sf -X POST "$CORTEX_URL/api/store" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "<COLLECTION>",
    "title": "<TITLE>",
    "text": "<CONTENT>"
  }' | jq .
```

For the `procedures` collection, FORGE format is REQUIRED:
- `text` MUST contain: `# Problema`, `# Procedura`, `# Enforcement Loop`
- `metadata` MUST include: `rule_id`, `has_enforcement_loop` (boolean true), `forge_version` ("2.0")

```bash
curl -sf -X POST "$CORTEX_URL/api/store" \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "procedures",
    "title": "<TITLE>",
    "text": "# Problema\n<PROBLEM>\n\n# Procedura\n<STEPS>\n\n# Enforcement Loop\n<ENFORCEMENT>",
    "metadata": {
      "rule_id": "<RULE_ID>",
      "has_enforcement_loop": true,
      "forge_version": "2.0"
    }
  }' | jq .
```

Returns `{"id": "<uuid>", "ok": true}` on success.

## Error handling

If any curl command fails or returns `{"error": ...}`:
1. Run cortex_health first
2. If health fails: report "Cortex is offline" to user
3. If health passes but operation fails: report the specific error message
4. If jq is not available: use `python3 -m json.tool` as fallback for formatting
