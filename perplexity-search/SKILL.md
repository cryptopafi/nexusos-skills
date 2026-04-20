---
name: perplexity-search
description: "Real-time web search via Perplexity Sonar Pro."
---

Real-time web search via Perplexity Sonar Pro. Use for current events, prices, facts, docs.

# Perplexity Web Search

```bash
KEY=$(security find-generic-password -s genie-keys -a perplexity-api -w)
curl -s https://api.perplexity.ai/chat/completions \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model": "sonar-pro", "messages": [{"role": "user", "content": "QUERY"}], "return_citations": true}'
```

Response: `choices[0].message.content` (answer) + `citations` (URLs).
