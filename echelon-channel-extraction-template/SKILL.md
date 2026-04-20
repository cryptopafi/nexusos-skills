---
name: echelon-channel-extraction-template
description: Use when onboarding a new ECHELON channel — generic extraction template to adapt per platform
---

# ECHELON {CHANNEL_NAME} — Procedura de Extracție Inteligentă

**Status**: DRAFT
**Data**: YYYY-MM-DD
**Versiune**: 1.0
**Regulă asociată**: ECHELON-S-001
**Procedure INSIGHT**: `~/.nexus/procedures/INSIGHT-PROCEDURE.md`
**Self-Improvement Cascade**: Ciclu 3 — Ingestion/ECHELON
**Scope**: Extracție inteligentă din {channel} — de la trigger la monitorizare

---

## Principiu

**Nu descărca tot. Descarcă inteligent.**

```
RESEARCH (Delphi) → TRIGGER → EXTRACT primul post → SCAN sursa (light) → FILTER valuable →
→ DEEP valuable → INSIGHT (Mode A/B/C) → STORE → DISPLAY → NOTIFY → REFERENCES → MONITOR → SELF-GRADE
```

---

## Self-Improvement Cascade (Ciclu 3: ECHELON)

Acest canal face parte din **Self-Improvement Cascade** (Cortex: `59ea880d`, `f5600d79`, `a2fd6230`).

### Pas 0: RESEARCH — Delphi Tool Discovery

**Înainte de orice extracție**, rulează Delphi research pe canalul target:

**Tool**: Delphi v2.2 (`~/repos/delphi/`)
**Cost**: Perplexity free tier + OpenRouter fallback
**Output**: `~/.nexus/echelon/{channel}/research/YYYY-MM-DD-tools-research.md`

**Ce investighezi**:
1. **Tool landscape** — Ce API-uri/tools există pentru acest canal? (pricing, rate limits, auth)
2. **Data availability** — Ce date poți extrage? (text, engagement, media, metadata)
3. **API changes** — Schimbări recente de API/pricing? (Reddit Nov 2025 crackdown, etc.)
4. **Best practices** — Cum extrag alții? (community patterns, gotchas)
5. **Cost optimization** — Care combinație tool oferă best value?

**Delphi queries sugerate**:
```
- "{channel} scraping API tools 2026 comparison"
- "{channel} API rate limits pricing changes"
- "{channel} data extraction best practices"
- "free alternatives to {channel} API"
```

**Output format**: Research doc cu tool comparison matrix, verdict, recommended stack.

### Self-Grade (la finalul implementării canalului)

După ce pipeline-ul e funcțional, aplică Self-Improvement Cascade flow complet:

```
RESEARCH (Delphi) ✅ → INGEST (tool testing) ✅ → INSIGHT (procedure creation) ✅ →
→ SELF-GRADING → STANDARDIZE
```

**Self-Grading checklist** (scorare 0-100):
| Criteriu | Puncte | Cum verifici |
|----------|--------|-------------|
| Tool stack testat live (nu doar docs) | 15 | Cel puțin 3 API calls reale per tool |
| Cost estimate bazat pe date reale | 10 | Run real → cost real, nu estimate din docs |
| Filter logic testată pe date reale | 15 | N posts reale → filter → verificare manuală |
| INSIGHT integration funcțională | 10 | Cel puțin 1 post enriched end-to-end |
| Enforcement loop complet (WHERE/WHEN/HOW/CONNECT) | 15 | META-H-002 compliance check |
| Error handling per pas documentat | 10 | Fiecare pas are fallback |
| Monitoring/watchlist funcțional | 10 | Cel puțin 1 entry în watchlist |
| Cortex store funcțional | 10 | Cel puțin 1 entry în `intelligence` collection |
| Pipeline script implementat | 5 | `{channel}-enrich.js` există și rulează |

**Rating**: ≥85 EXCELLENT | 70-84 GOOD | 50-69 NEEDS WORK | <50 REDO

**Output**: Scor + findings → Cortex `procedures` collection + `AUDIT-IMPROVEMENT-CYCLE.md` AUD-06.

---

## Flux Complet

### Pas 1: TRIGGER — De unde vine conținutul?

| Sursă | Cum ajunge | Frecvență |
|-------|-----------|-----------|
| **Manual** — Pafi trimite un link | Direct în pipeline | Ad-hoc |
| **Radar** — Monitorizare surse | Radar detectează post nou → queue | Automat |
| **Search** — Trending pe topics | {tool} search keywords + min engagement | Automat |
| **Cross-channel** — Referință din alt canal | Alt canal menționează conținut | Ad-hoc |

**DEDUP GATE** (obligatoriu, înainte de processing):
1. Cortex search: `POST /api/search {"query":"<url>","collection":"intelligence","limit":1}`
2. Score > 0.95 + URL match → SKIP
3. Altfel → procesează

---

### Pas 2: EXTRACT — Descarcă integral primul post

**Tool**: {tool_name}
**Cost**: {cost}
**Timp**: {timp}

**Ce obții**: {lista}

**Decizie automată**:
```
IF engagement_score > {threshold}:
    → Pas 3 (SCAN sursa)
ELSE:
    → Pas 5 direct (INSIGHT doar acest post)
```

Engagement score = {formula documentată aici}

---

### Pas 3: LIGHT SCAN — Baleiază sursa

**Tool**: {tool_name}
**Cost**: {cost}
**Timp**: {timp}

**Ce obții**: {lista}

---

### Pas 4: FILTER — Identifică posturi valoroase

**Tool**: Local (zero cost)
**Cost**: $0.00

**Criterii**:
```javascript
function isValuable(post) {
  // Channel-specific filter logic
  // Return true/false
}
```

---

### Pas 5: DEEP EXTRACT valuable posts

**Tool**: {tool_name}
**Cost**: {cost per post}

**Când e necesar** (vs light scan care deja are textul):
- {criteriu 1}
- {criteriu 2}

**Când NU e necesar**:
- {criteriu 1}

---

### Pas 6: ENRICH — CALL INSIGHT Procedure

**Procedură**: `~/.nexus/procedures/INSIGHT-PROCEDURE.md`

**Routing (Dual-Layer)**:
- engagement_score > 5000 OR manual_flag="opus" → **INSIGHT Mode A-Deep** (Opus — claims verification, entity discovery)
- engagement_score > {threshold} OR content_type in [article, video_transcript] → **INSIGHT Mode A-Standard** (Gemini Flash — rapid, free)
- Top N posts din scan → **INSIGHT Mode B** (Gemini Flash — batch overview)
- Restul valuable → **INSIGHT Mode C** (metrics only, no AI)

**Input contract**: INSIGHT §2 — acest canal furnizează:
- `content` = text complet
- `channel` = "{channel_id}"
- `engagement_score` = {formula}
- `content_type` = "{types}"

---

### Pas 7: STORE + DISPLAY + NOTIFY + MONITOR

#### Store:
```
Cortex: collection=intelligence
  metadata: channel={channel_id}, author, engagement, relevance_score, tags
Local: ~/.nexus/echelon/{channel}/output/YYYY-MM-DD/
```

#### Display (INSIGHT §5.1.1):
După store, Genie afișează insight-ul structurat în terminal (Mode A/B).
Mode C = silent, nu se afișează.

#### Notify (INSIGHT §5.1.2):
Trimite Telegram notification cu sumar concis.
Format: canal, autor, engagement, sentiment, key signals, action items, cortex_id.

#### Reference Extraction (INSIGHT §5.2):
Dacă Mode A a detectat materiale referite → search free sources → ingest sau propune.

#### Monitor:
Watchlist: `~/.nexus/echelon/{channel}/watchlist.json`

---

## Error Handling per Pas

| Pas | Eroare posibilă | Acțiune |
|-----|----------------|---------|
| 2 | API fail/timeout | Retry 1x. Dacă fail → skip, log, continue |
| 3 | Scan fail | Skip scan → procesează doar postul original |
| 4 | Filter error | Default: toate = valuable (over-enrich) |
| 5 | Deep fail pe 1 post | Skip acel post, continue |
| 6 | Gemini fail | Fallback: Ollama → Mode C |
| 7 | Cortex unreachable | Queue local: `pending-cortex/`. Retry next run |

**Principiu**: Pipeline NEVER stops. Degradează grațios.

---

## Enforcement Loop (META-H-002)

### WHERE
- **WISH Step H** — Orice URL din acest canal care intră în pipeline
- **Pipeline script** — `{channel}-enrich.js`
- **LaunchAgent** — `com.echelon.{channel}-monitor`

### WHEN
- **Manual trigger**: Pafi trimite un link
- **Radar trigger**: Monitoring detectează post nou
- **Search trigger**: Topic search periodic

### HOW (violation detection)
- Pipeline completeness: log cu timestamps per pas → Pas 7 executat?
- Cortex audit: count(channel="{channel_id}") per zi vs expected
- INSIGHT gate: posts care au trecut filter dar nu au Cortex entry
- Watchlist staleness: `last_scan` > 48h → monitoring down
- **Runner**: `test-all-procedures.js` (daily) + `procedure-health-check.sh` (weekly) + Genie manual (PROC-H-001)

### CONNECT
- → `INSIGHT-PROCEDURE.md` (Pas 6)
- → Cortex (intelligence collection)
- → Radar (monitoring targets)
- → `{CHANNEL}-COMPLETE.md` (capabilities reference)
- → Daily Digest (Telegram summary)
- → ECHELON-S-001 (governing rule)

### Dependencies
| Componentă | Locație | Status |
|-----------|---------|--------|
| {API key} | Keychain: `{KEY_NAME}` | ❌/✅ |
| Gemini OAuth | `~/.gemini/settings.json` | ✅ |
| Cortex VPS | `100.81.233.9:6400` | ✅ |
| INSIGHT Procedure | `~/.nexus/procedures/INSIGHT-PROCEDURE.md` | ✅ |

### Metrics
| Metric | Target | Cum măsori |
|--------|--------|---
