---
name: echelon-reddit-extraction
description: Use when running ECHELON Reddit extraction to ingest subreddit intelligence into the pipeline
---

# ECHELON Reddit — Procedura de Extracție Inteligentă

**Status**: ACTIVE
**Data**: 2026-02-27
**Versiune**: 1.1
**Regulă asociată**: ECHELON-S-001
**Procedure INSIGHT**: `~/.nexus/procedures/INSIGHT-PROCEDURE.md` (cross-channel, standalone)
**Self-Improvement Cascade**: Ciclu 3, Canal 2 — Ingestion/ECHELON
**Scope**: Extracție inteligentă din Reddit — de la trigger la monitorizare

---

## Principiu

**Nu descărca tot. Descarcă inteligent.**

```
RESEARCH (Delphi) ✅ → TRIGGER → EXTRACT primul post → SCAN subreddit (light) →
→ FILTER valuable → DEEP valuable (comments) → INSIGHT (Gemini default / Opus high-value) →
→ STORE → DISPLAY → NOTIFY Telegram VPS → REFERENCES → MONITOR
```

Fiecare pas e un filtru. Doar ce trece de filtru merge mai departe.

---

## Self-Improvement Cascade (Ciclu 3, Canal 2)

### Cascade Flow
```
✅ RESEARCH — Delphi research pe Reddit tool landscape (6 primary tools + 8 alternatives)
✅ INGEST — Live testing: Arctic Shift posts/comments, .json endpoint, ScrapeCreators cross-Reddit search
✅ INSIGHT — Procedure creation (REDDIT-EXTRACTION-PROCEDURE.md + REDDIT-COMPLETE.md)
✅ STANDARDIZE — Enforcement loop, health-check registration, Cortex store pending
✅ SELF-GRADING — 85/100 (EXCELLENT). E2E test: Perplexity Computer → Cortex 42f15d3a
```

---

## Flux Complet (7 pași)

### Pas 1: TRIGGER — De unde vine conținutul?

| Sursă | Cum ajunge | Frecvență |
|-------|-----------|-----------|
| **Manual** — Pafi trimite un Reddit link | Direct în pipeline | Ad-hoc |
| **Radar** — Monitorizare subreddits | Arctic Shift periodic scan → queue | Automat, 2x/zi |
| **Search (per-sub)** — Top posts per subreddit | Arctic Shift `?subreddit=X&after=Y` sau .json `/top/.json?t=week` | Automat, 1x/zi |
| **Search (cross-Reddit)** — Topic discovery | ScrapeCreators `/v1/reddit/search?query=X&sort=relevance` ($0.002/query, 25 results cross-subreddit) | Automat, 1x/zi |
| **Cross-channel** — Referință din alt canal | X/YouTube/Newsletter menționează Reddit post | Ad-hoc |

**Output**: Un Reddit post URL sau post ID intră în pipeline.

#### Cross-Reddit Search (ScrapeCreators)

Singurul tool care face search **fără subreddit specificat**. Testat live:
```
GET https://api.scrapecreators.com/v1/reddit/search
  ?query=AI+agents+SaaS+automation
  &sort=relevance
Header: x-api-key: ${SCRAPECREATORS_KEY}
```
- **Cost**: 1 credit ($0.002) per query
- **Returns**: 25 posts cross-subreddit cu date complete (selftext, score, num_comments, upvote_ratio, subreddit_subscribers, flair, author)
- **Sort options**: `new` (cronologic) sau `relevance` (best match — aduce posturi cu engagement real)
- **Test result**: Query "AI agents SaaS automation" → posturi din r/AI_Agents (6037 score), r/ClaudeAI (567), r/Entrepreneur (1652), r/n8n (510)
- **Keychain**: `SCRAPECREATORS_KEY` (shared cu X channel)
- **Când**: Daily topic search pe 3-5 queries relevante. Cost: $0.006-$0.01/zi

**Queries sugerate pentru daily search**:
```
"claude AI agents automation"
"SaaS AI tools startup"
"MCP server AI integration"
"AI automation business workflow"
"LLM agents production deployment"
```

#### DEDUP GATE (Pas 1, înainte de orice processing)
1. Cortex search: `POST /api/search {"query":"<reddit_url>","collection":"intelligence","limit":1}`
2. Dacă `score > 0.95` și URL match exact → `SKIP` (deja procesat)
3. Dacă `score > 0.8` dar URL diferit → procesează (conținut similar, sursă diferită)
4. Log: `[DEDUP: skip|process|new]` pentru tracking

---

### Pas 2: EXTRACT — Descarcă integral primul post

**Tool**: Arctic Shift `/api/posts/search` sau .json endpoint
**Cost**: $0.00 (free)
**Timp**: ~1-2s

**Ce obții**:
- Title + selftext complet
- Score (net upvotes), num_comments
- Author, subreddit, flair
- Created UTC, permalink
- Post type (self, link, image, video)
- Crosspost parent (dacă e crosspost)

**Arctic Shift query (dacă ai post ID)**:
```
GET https://arctic-shift.photon-reddit.com/api/posts/ids?ids={post_id}
```

**.json query (dacă ai URL)**:
```
curl -s -A "ECHELON-bot/1.0" "https://old.reddit.com{permalink}.json"
```

**Decizie automată după extracție**:
```
IF score > threshold OR num_comments > 50:
    → Pas 3 (SCAN subreddit-ul)
ELSE IF post e long-form (selftext > 500 chars):
    → Pas 3 (SCAN subreddit-ul)
ELSE:
    → Pas 5 direct (INSIGHT doar acest post)
```

**Engagement score** = score + num_comments×5
**Threshold sugerat**: 200 (ajustabil per subreddit)

---

### Pas 3: LIGHT SCAN — Baleiază subreddit-ul

**Tool**: Arctic Shift `/api/posts/search` cu date range
**Cost**: $0.00 (free)
**Timp**: ~2-3s per request (max 100 results)

**Ce obții GRATUIT în light scan**:
- Title + selftext complet per post
- Score, num_comments per post
- Author per post
- Created UTC (timeline ordering)
- Flair (topic categorization)
- Post type indicators

**Parametri light scan**:
```
GET https://arctic-shift.photon-reddit.com/api/posts/search
  ?subreddit={subreddit_name}
  &after={7_days_ago_epoch}
  &before={now_epoch}
  &limit=100
  &sort=desc
```

**Alternativă .json pentru real-time (top din ultima săptămână)**:
```
curl -s -A "ECHELON-bot/1.0" "https://old.reddit.com/r/{sub}/top/.json?t=week&limit=100"
```

**Cost real testat**: 100 posts r/ClaudeAI = $0.00, ~2s, full metadata

---

### Pas 4: FILTER — Identifică posturi valoroase

**Tool**: Local Python (zero cost)
**Cost**: $0.00
**Timp**: <1s

**Criterii de filtrare (automate)**:

#### Tier A — Metrici (instant, zero AI):
```python
def is_valuable(post):
    score = post.get('score', 0) or 0
    num_comments = post.get('num_comments', 0) or 0
    selftext = post.get('selftext', '')
    title = post.get('title', '')

    # Skip removed/deleted
    if selftext in ['[removed]', '[deleted]']:
        return False

    # High engagement
    if score > 50 or num_comments > 20:
        return True

    # Long-form content (detailed posts are often valuable)
    if len(selftext) > 1000:
        return True

    # Engagement rate (score per comment)
    if num_comments > 5 and score / max(num_comments, 1) > 3:
        return True

    return False
```

#### Tier B — Relevanță topic (Ollama, optional):
```
Ollama qwen2.5:7b: "Is this Reddit post relevant to AI, SaaS, market intelligence,
Claude, automation, or business tools? Answer YES or NO only: <title> <selftext[:500]>"
```
Cost: $0.00 (local), ~0.5s/post

**Estimare filtrare**: Din 100 posts → **~25-35 valuable** (25-35% rata — Reddit e mai topic-focused decât X)

---

### Pas 5: DEEP EXTRACT — Descarcă comentariile valoroase

**Tool**: Arctic Shift `/api/comments/tree`
**Cost**: $0.00 (free)
**Timp**: ~2-5s per post (depending on comment count)

**Când e necesar deep extract** (comentariile adaugă valoare):
- Post are >20 comentarii (discuție activă)
- Post e o întrebare/cerere de ajutor (răspunsurile sunt valoarea)
- Post e controversat (score volatile, multe comentarii)
- Post e un "Show HN"-style showcase (feedback în comments)

**Când NU e necesar** (selftext e suficient):
- Post e un link extern (valoarea e în link, nu comments)
- Post are <5 comentarii
- Post e announcement/news (text e valoarea)

**Query**:
```
GET https://arctic-shift.photon-reddit.com/api/comments/tree
  ?link_id=t3_{post_id}
  &limit=500
```

**Parsing comment tree** (Reddit nested structure):
```python
def extract_comments(tree, min_score=5):
    valuable = []
    for item in tree:
        data = item.get('data', item)
        author = data.get('author', '')
        body = data.get('body', '')
        score = data.get('score', 0)

        # Skip deleted, AutoModerator, low score
        if author in ['[deleted]', 'AutoModerator'] or not body:
            continue
        if score >= min_score:
            valuable.append({
                'author': author,
                'body': body,
                'score': score
            })

        # Recurse into replies
        replies = data.get('replies', {})
        if isinstance(replies, dict):
            children = replies.get('data', {}).get('chi
