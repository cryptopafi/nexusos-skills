---
name: auto-cortex-sync
description: "Auto-sync local memory files to Cortex KB"
---

Auto-sync local memory files to Cortex KB

# Auto Cortex Sync — Skill

**ID:** `auto-cortex-sync`
**Version:** 1.0.0
**Created:** 2026-02-19
**Owner:** Richard

---

## Purpose

Sincronizare automată între memoria internă a agentului și Cortex KB. Orice informație salvată local este automat replicată în Cortex pentru cross-agent access.

---

## Trigger

- **Implicit:** După fiecare salvare în fișiere locale (MEMORY.md, skills/, procedures/)
- **Manual:** `run-tool.sh cortex-sync`

---

## What Syncs

| Local | Cortex Collection | Metada
