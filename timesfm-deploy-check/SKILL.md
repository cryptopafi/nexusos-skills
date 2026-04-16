---
name: timesfm-deploy-check
description: Check if ECHELON signal-aggregator has 60+ days of data and deploy TimesFM
---

TimesFM Deployment Check — 60-day data collection window complete.

The ECHELON signal-aggregator daemon (`com.echelon.signal-aggregator`, LaunchAgent on MacM4) has been running daily at 23:55 since 2026-04-04, appending one row per day to `~/.nexus/monitoring/events/echelon-daily-counts.jsonl`.

Tasks:
1. Verify data collection: `wc -l ~/.nexus/monitoring/events/echelon-daily-counts.jsonl` should show 60+ rows
2. Check data quality: `tail -5 ~/.nexus/monitoring/events/echelon-daily-counts.jsonl` should have recent dates with non-zero channel counts
3. If >= 32 rows: proceed to deploy TimesFM (D-010 from Dispatch Plan v2.1):
   - Clone status check: `~/repos/watchlist/timesfm` should exist
   - Install timesfm in Python 3.12 venv: `source ~/repos/watchlist/.py312-venv/bin/activate && pip install timesfm[torch]`
   - Run system preflight: `python3 ~/repos/watchlist/timesfm/scripts/check_system.py`
   - Write deployment script that: loads daily counts, feeds to TimesFM, outputs 7-day forecast per channel
   - Wire into ECHELON morning brief
4. If < 32 rows: investigate aggregator failures (`~/.nexus/logs/signal-aggregator.log`), extend wait period, reschedule this task
5. Reference: ~/.nexus/intel/reports/dispatch-plan-20260404-v2.md (D-010 section) and Cortex ID 694db5b9 (TimesFM evaluation)

Also check: has Python 3.12 environment drifted? Re-verify `python3 --version` on MacM4.