---
name: radar-echelon-integration
description: Use when wiring RADAR-discovered sources into ECHELON watchlists and BI pipelines
---

PROCEDURE: RADAR-ECHELON-INTEGRATION v1.0

## Problema
Fara aceasta procedura, sursele noi descoperite in NEXUS/BI raman izolate in sources.json si nu ajung in ECHELON watchlist-uri. Invers, canalele descoperite de ECHELON nu sunt inregistrate in Radar.

## Procedura
6 pasi: (1) adaugare manuala via /radar-add Telegram, (2) auto-add NEXUS EPR>=14 hook, (3) sync Radar->ECHELON watchlist YouTube, (4) ECHELON->Radar discovery feedback, (5) sync bidirectional radar-sync.py, (6) verificare stare completa.

## Enforcement
Post-H dupa orice radar-add. Zilnic in echelon-orchestrate.sh pre-run. Saptamanal review complet.
FILE: ~/.nexus/procedures/RADAR-ECHELON-INTEGRATION.md
