---
name: echelon-twitter-extraction
description: Use when running ECHELON X/Twitter extraction v1.3 to ingest Twitter intelligence into the pipeline
---

# ECHELON X/Twitter — Procedura de Extracție Inteligentă

**Status**: ACTIVE
**Data**: 2026-02-27
**Versiune**: 1.3
**Regulă asociată**: ECHELON-S-001
**Procedure INSIGHT**: `~/.nexus/procedures/INSIGHT-PROCEDURE.md` (cross-channel, standalone)
**Self-Improvement Cascade**: Ciclu 3, Canal 1 — Ingestion/ECHELON
**Scope**: Extracție inteligentă din X/Twitter — de la trigger la monitorizare

---

## Principiu

**Nu descărca tot. Descarcă inteligent.**

```
TRIGGER → DEEP primul post → SCAN cont (light) → FILTER valuable →
→ DEEP valuable → INSIGHT (Gemini default / Opus high-value) → STORE →
→ DISPLAY → NOTIFY Telegram VPS → REFERENCES → MONITOR ongoing
```

Fiecare pas e un filtru. Doar ce trece de filtru merge mai departe.

---

## Flux Complet (7 pași)

### Pas 1: TRIGGER — De unde vine link-ul?

| Sursă | Cum ajunge | Frecvență |
|-------|-----------|-----------|
| **Manual** — Pafi trimite un link | Direct în pipeline | Ad-hoc |
| **Radar** — Monitorizare conturi | Radar detectează post nou → queue | Automat, 3x/zi |
| **Search** — Trending pe topics | Apify search keywords + min engagement | Automat, 1x/zi |
| **Cross-channel** — Referință din alt canal | YouTube/Reddit/Newsletter menționează tweet | Ad-hoc |

**Output**: Un tweet URL intră în pipeline.

#### DEDUP GATE (Pas 1, înainte de orice processing)
1. Cortex search: `POST /api/search {"query":"<tweet_url>","collection":"intelligence","limit":1}`
2. Dacă `score > 0.95` și URL match exact → `SKIP` (deja procesat)
3. Dacă `score > 0.8` dar URL diferit → procesează (conținut similar, sursă diferită)
4. Log: `[DEDUP: skip|process|new]` pentru tracking

---

### Pas 2: DEEP EXTRACT — Descarcă integral primul post

**Tool**: ScrapeCreators `/v1/twitter/tweet`
**Cost**: 1 credit ($0.002)
**Timp**: ~2s

**Ce obții**:
- Text complet (inclusiv X Articles 20K+ chars cu formatting)
- Engagement: views, likes, retweets, replies, bookmarks, quotes
- Media: photos URLs, video URLs + bitrates
- Author: screen_name, followers, verified status
- Conversation ID (pentru thread extraction ulterior)
- Entities: URLs, hashtags, mentions

**Decizie automată după extracție**:
```
IF engagement_score > threshold:
    → Pas 3 (SCAN contul autorului)
ELSE IF post e X Article sau thread:
    → Pas 3 (SCAN contul)
ELSE:
    → Pas 5 direct (ENRICH doar acest post, skip scan)
```

Engagement score = likes + retweets×3 + bookmarks×2
Threshold sugerat: 500 (ajustabil)

---

### Pas 3: LIGHT SCAN — Baleiază contul autorului

**Tool**: Apify `usersFromUsers`
**Cost**: ~$0.002-0.004 CU (200 tweets)
**Timp**: ~17s

**Ce obții GRATUIT în light scan** (fără deep extraction):
- Text COMPLET al fiecărui tweet (nu doar titlu)
- TOATE metricsele: views, likes, retweets, replies, bookmarks, quotes
- Date (timeline ordering)
- Media indicators
- Conversation IDs (thread detection)
- Reply indicators (original post vs reply)

**Parametri light scan**:
```json
{
  "usersFromUsers": ["<author_screen_name>"],
  "numberOfTweets": 200,
  "search_type": "Latest"
}
```

**Cost real testat**: 200 tweets @heynavtoor = $0.002, 16.8s, 406KB
Primești tot textul — nu e nevoie să plătești extra pentru "titluri".

---

### Pas 4: FILTER — Identifică posturi valoroase

**Tool**: Local Python (zero cost) sau Ollama qwen2.5:7b (zero cost, local)
**Cost**: $0.00
**Timp**: <1s (Python) sau ~3s (Ollama)

**Criterii de filtrare (automate)**:

#### Tier A — Metricile (instant, zero AI):
```python
def is_valuable(tweet):
    likes = tweet.get('favorites', 0) or 0
    bookmarks = tweet.get('bookmarks', 0) or 0
    retweets = tweet.get('retweets', 0) or 0
    views = tweet.get('views', 0) or 0
    text = tweet.get('text', '')

    # Skip replies (nu sunt content original)
    if text.startswith('@'):
        return False

    # Engagement thresholds
    if likes > 50 or bookmarks > 10 or retweets > 20:
        return True

    # High engagement rate (views > 1000 dar likes/views > 2%)
    if views > 1000 and likes / max(views, 1) > 0.02:
        return True

    return False
```

#### Tier B — Relevanță topic (Ollama, optional):
Dacă vrei și filtrare pe relevanță pentru topicurile noastre:
```
Ollama qwen2.5:7b: "Is this tweet relevant to AI, SaaS, market intelligence,
or business automation? Answer YES or NO only: <tweet_text>"
```
Cost: $0.00 (local), ~0.5s/tweet, batch de 30 tweets = ~15s

**Rezultat testat**: Din 200 tweets → 67 posturi originale → **37 valuable** (18.5% rata)

---

### Pas 5: DEEP EXTRACT valuable posts

**Tool**: ScrapeCreators `/v1/twitter/tweet` (per post valuable)
**Cost**: 1 credit/post ($0.002)
**Timp**: ~2s/post

**Când e necesar deep extract** (vs light scan care deja are textul):
- Post e X Article (long-form cu formatting, headers, bold)
- Post are video (trebuie video URLs + transcript)
- Post are media complexă (carousel, PDF preview)
- Vrei entities complete (toate URL-urile expandate)

**Când NU e necesar** (light scan e suficient):
- Tweets scurte (<280 chars) — textul complet e deja în light scan
- Nu au media sau doar o poză
- Doar vrei insight pe text, nu pe attachments

**Estimare**: Din 37 valuable, ~10-15 merită deep extract (X Articles, threads, video).
**Cost**: 10-15 credite ($0.02-0.03)

---

### Pas 6: ENRICH — CALL INSIGHT Procedure (Dual-Layer)

**Procedură**: `~/.nexus/procedures/INSIGHT-PROCEDURE.md` v1.2 (standalone, cross-channel)

**Routing Dual-Layer (definit în INSIGHT §3)**:
- engagement_score > 5000 OR manual_flag="opus" → **Mode A-Deep (Opus)** — claims verification reală, entity discovery, bias detection (~$0.15-0.20/post, ~90s)
- engagement_score > 2000 OR content_type in [article, thread] → **Mode A-Standard (Gemini Flash)** — analiză rapidă, 10 secțiuni ($0.00, ~8s)
- Top 10 posts din light scan → **Mode B (Gemini Flash)** — batch overview ($0.00)
- Restul valuable → **Mode C** — metrics-only store, fără AI ($0.00)

**Input contract**: Vezi INSIGHT §2 — X-EXTRACTION furnizează:
- `content` = textul tweet/article
- `channel` = "x-twitter"
- `engagement_score` = likes + retweets×3 + bookmarks×2
- `content_type` = "tweet" | "article" | "thread"

**Output**: Intelligence enriched → Cortex `intelligence` collection (prin INSIGHT §5)

---

### Pas 7: STORE + DISPLAY + NOTIFY + REFERENCES + MONITOR

#### Store (per post enriched):
```
Cortex: collection=intelligence
  metadata: channel=x-twitter, author, engagement, relevance_score, tags,
            model (gemini-2.5-flash | claude-opus-4-6), insight_layer (standard | deep)
Local: ~/.nexus/echelon/x/output/YYYY-MM-DD/
```

#### Display (INSIGHT §5.1.1):
După store, afișează insight-ul structurat în terminal (Mode A-Standard + A-Deep).
Mode C = silent, nu se afișează.

#### Notify (INSIGHT §5.1.2):
Trimite pe Telegram **exclusiv VPS bot** (@Caludeintelbot).
Format: canal, autor, engagement, sentiment, key signals, action items, cortex_id.

#### Reference Extraction (INSIGHT §5.2):
Dacă Mode A a detectat materiale referite (cărți, papers, cursuri) →
search free sources (ArXiv, YouTube, GitHub) → ingest automat sau propune achiziție pe Telegram.

#### Monitor (pentru conturi identificate ca valoroase):
Adaugă autorul în **watch list** (`~/.nexus/echelon/x/watchlist.json`):
```json
{
  "heynavtoor": {
    "added": "2026-02-27",
    "reason": "Claude Cowork analysis, high bookmark rate",
    "last_scan": "2026-02-27",
    "last_tweet_id": "2027054100807106829",
    "scan_frequency": "daily",
    "filter": "likes > 50 OR bookmarks > 10"
  }
}
```

**Monitoring cycle** (LaunchAgent daily):
1. Pentru fiecare cont din watchlist:
   - Apify `usersFromUsers` + `timeSinceId` (doar tweets noi de la ultima scanare)
   - Cost: ~$0.001/cont/zi (doar tweets noi, nu full timeline)
2. Filter valuable (Pas 4)
3. Deep extract + enrich doar ce trece filtrul
4. Update `last_tweet_id` în watchlist

**Cost monitoring ongoing**: ~$0.001/cont/zi × 30 conturi = **$0.03/zi = $0.90/lună**

---

## Cost Total per Scenariu

### Scenariu A: Un link manual de la Pafi

| Pas | Acțiune |
