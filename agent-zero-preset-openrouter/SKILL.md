---
name: agent-zero-preset-openrouter
description: "Apply and recover Agent Zero OpenRouter preset safely (JSON fix, restart, rollback)"
---

Apply and recover Agent Zero OpenRouter preset safely (JSON fix, restart, rollback)

# Agent Zero Preset OpenRouter

## Problem
Applying Agent Zero preset can corrupt `settings.json` (literal `\\n` EOF) and fail restart path.

## Solution Steps
1. Check current settings without exposing secrets:
```bash
bash /Users/pafi/.openclaw/scripts/agent-zero-preset-openrouter.sh show
```
2. Ensure `.env` has `API_KEY_OPENROUTER` present (do not print value).
3. Apply balanced preset:
```bash
bash /Users/pafi/.openclaw/scripts/agent-zero-preset-openrouter.sh apply balanced
```
4. Validate 
