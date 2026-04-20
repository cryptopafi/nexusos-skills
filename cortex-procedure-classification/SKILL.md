---
name: cortex-procedure-classification
description: Use when classifying or tagging procedures in Cortex using the canonical architecture taxonomy
---

Cortex Procedure Classification System v1

## Tag-uri standard (metadata.architecture)

### MODULAR (proceduri noi, standardizate)
- Construite manual de Genie/Pafi
- Folosesc pattern-uri LEGO composable
- Au faze clare, input/output definit, sunt reutilizabile
- Pot fi combinate între ele sub alte proceduri
- Exemplu: Pre-Execution Audit, Delivery Audit, Self-Improvement Cascade, Genie-Codex Protocol
- Tag metadata: `"architecture": "modular", "version": "X.Y"`

### INGESTED (proceduri auto-extrase din surse externe)
- Extrase automat din Skool, Coursera, YouTube, web
- Calitate variabilă — unele utile, altele generic/low-value
- NU au fost validate de Genie sau Opus
- Pot fi promovate la MODULAR după INSIGHT + standardizare
- Tag metadata: `"architecture": "ingested", "source": "skool|coursera|youtube|web"`

### LEGACY (proceduri vechi, pre-framework)
- Create înainte de Self-Improvement Cascade
- Nu urmează pattern-uri standardizate
- Pot fi refactorizate la MODULAR când sunt relevante
- Tag metadata: `"architecture": "legacy"`

## Reguli
1. Orice procedură nouă creată de Genie → tag `modular`
2. Orice procedură auto-extrasă din ingestie → tag `ingested`
3. Procedurile existente fără tag → implicit `legacy`
4. Promovare: `ingested` → INSIGHT Opus → dacă valoroasă → refactor → `modular`
5. Deprecare: `legacy` → review periodic → fie upgrade la `modular`, fie archive
6. Cortex search: când Genie caută proceduri, prioritizează `modular` > `legacy` > `ingested`
