---
name: cortex-first-gate
description: Use before any external tool call to enforce Cortex-first discipline — check knowledge base first
---

Cortex-First Gate — Procedură Standard de Operare

Status: ACTIVE | Versiune: 1.0 | Creat: 2026-02-28 | Regulă asociată: PROC-H-001 | Scope: Genie verifică Cortex înainte de orice acces la tool extern sau serviciu extern.

## 1. Problema
Fără această procedură, Genie accesează direct tool-uri externe (WebFetch, WebSearch) pentru lucruri care există deja ca proceduri în Cortex. Timp pierdut, Pafi trebuie să corecteze.
Situații acoperite: orice cerere despre un tool/serviciu extern, orice workflow care ar putea fi acoperit de o procedură existentă, orice task cu keyword recognoscibil (site name, API name, tool name).

## 2. Procedura
Pas 1 — Extrage keywords: numele tool-ului sau serviciului din cererea utilizatorului.
Pas 2 — Search Cortex procedures:
  ssh pafi@89.116.229.189 curl -s -X POST http://localhost:6400/api/search -H Content-Type:application/json -d {query:KEYWORDS,collection:procedures,limit:3}
Pas 3 — Evaluează scorul: >=0.7 folosește direct, 0.5-0.7 folosește ca bază, <0.5 continuă cu WebFetch.
Pas 4 — Aplică procedura găsită fără tool-uri externe suplimentare.

## 3. Cortex Logging
După fiecare execuție: loghează hit/miss în procedure-health.json (procedure: CORTEX-FIRST-GATE, result: hit/miss, score: X.XX).

## 4. Enforcement Loop
WHERE: WISH Step I.1 — obligatoriu înainte de orice search extern
WHEN: La fiecare task care menționează un tool/serviciu/site extern
HOW: Dacă Genie face WebFetch/WebSearch fără search Cortex prealabil → violation PROC-H-001. Detection: Genie auto-check la post-H.
CONNECT: PROC-H-001 → WISH I.1 → acest gate; META-H-002 → FORGE template aplicat la salvare; procedure-health.json → entry CORTEX-FIRST-GATE

## 5. Dependențe
Cortex API: http://localhost:6400/api/search | SSH: pafi@89.116.229.189 | WISH framework: CLAUDE.md Step I.1
