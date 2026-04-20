---
name: cortex-api-restart-procedure
description: Use when Cortex API on port 6400 fails to start after reboot — systemd recovery with exact commands
---

# Problema
Cortex API (port 6400) did not start after VPS reboot. Qdrant container was up but Cortex Bun process was not. Systemd unit existed at /etc/systemd/system/cortex.service but was in disabled state.
# Procedura
1. Check: sudo systemctl status cortex shows disabled
2. Fix: sudo systemctl enable cortex
3. Start: sudo systemctl start cortex
4. Verify: curl -s http://localhost:6400/api/health returns ok with 102 collections
# Enforcement Loop
Reboot test must always check Cortex health. Added to nightly audit script.
