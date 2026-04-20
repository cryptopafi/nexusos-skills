---
name: grok-analysis
description: "Long-context analysis via Grok (2M tokens)."
---

Long-context analysis via Grok (2M tokens). Use for large documents, PDFs, datasets.

# Grok Analysis (via OpenRouter)

```bash
curl -s https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer ${OPENROUTER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model": "x-ai/grok-3-mini-beta", "messages": [{"role": "user", "content": "ANALYZE: [content]"}]}'
```

2M context window. Use when content exceeds normal limits.
