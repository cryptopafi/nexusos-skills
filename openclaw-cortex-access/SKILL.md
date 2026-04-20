---
name: openclaw-cortex-access
description: "Restore OpenClaw agent access to Cortex via gateway config and fallback web_fetch pattern"
---

Restore OpenClaw agent access to Cortex via gateway config and fallback web_fetch pattern

# OpenClaw Cortex Access

## Problem
OpenClaw agents cannot use Cortex because gateway config lacks Cortex integration and/or required tool permissions.

## Solution Steps
1. Open gateway config file (reference used in procedure):
```bash
cat /Users/pafi/.claude/projects/-Users-pafi/memory/openclaw-configs/gateway-1-production.json
```
2. Ensure agents can use web fetch path for Cortex calls (temporary stopgap).
3. Ensure agent defaults include Cortex access metadata/instructions.
4. Ensure Cort
