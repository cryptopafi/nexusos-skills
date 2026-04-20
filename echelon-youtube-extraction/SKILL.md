---
name: echelon-youtube-extraction
description: Use when running ECHELON YouTube extraction to ingest channel intelligence into the pipeline
---

# ECHELON YouTube — Procedura de Extractie Inteligenta

**Status**: ACTIVE
**Data**: 2026-02-27
**Versiune**: 1.0
**Regula asociata**: ECHELON-S-001
**Procedure INSIGHT**: `~/.nexus/procedures/INSIGHT-PROCEDURE.md` (cross-channel, standalone)
**Self-Improvement Cascade**: Ciclu 3, Canal 3 -- Ingestion/ECHELON
**Scope**: Extractie inteligenta din YouTube -- de la trigger la monitorizare

---

## Principiu

**Nu descarca tot. Descarca inteligent.**

```
RESEARCH (Delphi) ✅ -> TRIGGER -> EXTRACT video metadata -> SCAN channel (light) ->
-> FILTER valuable -> DEEP valuable (transcript) -> INSIGHT (Gemini default / Opus high-value) ->
-> STORE -> DISPLAY -> NOTIFY Telegram VPS -> REFERENCES -> MONITOR
```

Fiecare pas e un filtru. Doar ce trece de filtru merge mai departe.

---

## Self-Improvement Cascade (Ciclu 3, Canal 3)

### Cascade Flow
```
✅ RESEARCH -- Tool landscape research (6 tools tested: yt-dlp, ScrapeCreators, RSS, YouTube API v3, MCP transcript, Invidious)
✅ INGEST -- Live testing: yt-dlp metadata, ScrapeCreators video+channel+search, RSS feed, MCP transcript
✅ INSIGHT -- Procedure creation (YOUTUBE-EXTRACTION-PROCEDURE.md + YOUTUBE-COMPLETE.md)
✅ STANDARDIZE -- Enforcement loop, health-check registration, watchlist
⬜ SELF-GRADING -- Pending (de rulat dupa youtube-enrich.js implementat)
```

---

## Flux Complet (7 pasi)

### Pas 1: TRIGGER -- De unde vine continutul?

| Sursa | Cum ajunge | Frecventa |
|-------|-----------|-----------|
| **Manual** -- Pafi trimite un YouTube link | Direct in pipeline | Ad-hoc |
| **Radar** -- Monitorizare canale (RSS) | RSS poll detecteaza video nou -> queue | Automat, 4x/zi |
| **Search** -- Trending pe topics | ScrapeCreators search keywords + min engagement | Automat, 1x/zi |
| **Cross-channel** -- Referinta din alt canal | X/Reddit/Newsletter mentioneaza video | Ad-hoc |

**Output**: Un YouTube video URL intra in pipeline.

#### New Video Detection (RSS-based, FREE)
Monitorizarea se face prin YouTube RSS feed -- zero cost, zero auth:
```
GET https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}
```
- Returns: ~15 most recent videos cu videoId, title, published date, description
- Poll frequency: every 6h (4x/zi)
- Detect new: compare videoId list vs last known video IDs in watchlist
- Cost: $0.00

#### Topic Search (ScrapeCreators, paid)
```
GET https://api.scrapecreators.com/v1/youtube/search?query={keywords}
Header: x-api-key: ${SCRAPECREATORS_KEY}
```
- Returns: videos + shorts + channels + lives (19+ results tested)
- Cost: 1 credit ($0.002) per query
- Frequency: 3-5 queries/zi pe topics relevante

**Queries sugerate pentru daily search**:
```
"claude AI automation agents 2026"
"AI SaaS tools startup launch"
"MCP server AI integration tutorial"
"LLM agents production deployment"
"AI business workflow automation"
```

#### DEDUP GATE (Pas 1, inainte de orice processing)
1. Cortex search: `POST /api/search {"query":"<youtube_url>","collection":"intelligence","limit":1}`
2. Daca `score > 0.95` si URL match exact -> `SKIP` (deja procesat)
3. Daca `score > 0.8` dar URL diferit -> proceseaza (continut similar, sursa diferita)
4. Log: `[DEDUP: skip|process|new]` pentru tracking

---

### Pas 2: EXTRACT -- Descarca metadata video

**Tool**: yt-dlp `--skip-download --dump-json` (PRIMARY, FREE)
**Cost**: $0.00
**Timp**: ~3-5s

**Ce obtii**:
- Title, description completa
- Views, likes, comment_count
- Duration (seconds)
- Channel name, channel_id, channel_follower_count
- Tags (array), categories
