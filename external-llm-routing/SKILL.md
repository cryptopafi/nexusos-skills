---
name: external-llm-routing
description: "Route specialized tasks to Grok, Perplexity, Gemini, or Ollama with cost and fallback controls"
---

Route specialized tasks to Grok, Perplexity, Gemini, or Ollama with cost and fallback controls

# External LLM Routing

## Purpose
Use the cheapest/safest model that still matches the task objective, with deterministic fallback.

## Decision Table
| Task Type | Preferred Provider/Model | Why | Cost Guard |
|---|---|---|---|
| Social copy, hooks, X/Twitter virality | OpenRouter `x-ai/grok-3-beta` | Strong social tone + trend style | Use only for final copy pass, not bulk drafts |
| Real-time web research with sources | OpenRouter `perplexity/sonar-pro` | Best citation-style search output | 
