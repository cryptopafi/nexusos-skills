---
name: launchagent-bash-hardening
description: Use when LaunchAgent scripts fail or exit non-zero due to bash edge-cases and pipefail issues
---

## 1. Problema
Mai multe LaunchAgent scripturi returnau exit non-zero din cauza edge-case-urilor bash (`set -euo pipefail`, array expansion, pipeline failures), ceea ce bloca monitorizarea automata.
## 2. Procedura
Am aplicat patch-uri punctuale: normalizare `grep -c` output in `codex-watchdog.sh`, fallback non-fatal pe pipeline-ul `BLOCKED_TASKS`, empty-array expansion compatibil bash 3.2 in `ingest-source.sh`, restructurare check securitate in `nightly-audit.sh`. Am validat runtime pentru `youtube-enrich.js --monitor` si `test-all-procedures.js --tier daily`.
## 3. Context
Task: m4-180 (Nexus CH-02). Mediu: MacM4.
## 4. Enforcement Loop
WHERE: verificare zilnica in LaunchAgents + `test-all-procedures.js`. WHEN: dupa fiecare patch pe scripturi operationale. HOW: comenzi manuale cu verificare explicita `exit code == 0`. CONNECT: reguli DEV-H-010 si META-H-001 pentru livrari cu validare runtime.
