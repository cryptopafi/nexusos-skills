---
name: nightly-audit-run
description: "Run nightly operational audit and deliver a Telegram health report"
---

Run nightly operational audit and deliver a Telegram health report

# Nightly Audit Run

## Purpose
Execute a deterministic 7-step health check, produce a text report, and notify Pafi on Telegram.

## Procedure
1. Check OpenClaw gateway status on port `18789`.
```bash
GATEWAY_HEALTH="$(curl -sS http://127.0.0.1:18789/health 2>/dev/null || curl -sS http://127.0.0.1:18789/status 2>/dev/null || echo 'gateway-unreachable')"
```
2. Check Cortex health on VPS.
```bash
CORTEX_HEALTH="$(ssh -o BatchMode=yes -o ConnectTimeout=8 pafi@89.116.229.189 'curl -sS http://localh
