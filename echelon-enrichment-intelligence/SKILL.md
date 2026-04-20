---
name: echelon-enrichment-intelligence
description: Use when running ECHELON cross-channel enrichment pipeline to ingest and enrich intelligence
---

# INSIGHT — Procedură de Enrichment Intelligence (Cross-Channel)

**Status**: ACTIVE
**Creat**: 2026-02-27
**Versiune**: 1.2
**Regulă asociată**: ECHELON-S-001
**Scope**: Orice conținut din orice canal ECHELON care trece de filtrare → enrichment standardizat

---

## 1. Problema

Conținutul extras din canale (X, YouTube, Reddit, LinkedIn, Newsletter, etc.) vine ca raw data — text + metrici. Fără enrichment, e doar noise. INSIGHT transformă raw data în intelligence actionabilă prin:
- Structured analysis (9 secțiuni standard)
- Scoring (relevance, sentiment, urgency)
- Entity extraction (people, companies, products, technologies)
- **Reference extraction** (books, papers, courses, tools → search free sources → ingest or propose purchase)
- Action items generation
- Cross-reference cu existing knowledge (Cortex)

### De ce e procedură separată (nu embedded în fiecare canal)
- **Reusable**: Aceeași logică se aplică pe X, YouTube, Reddit, orice canal
- **Updatable**: Schimbarea modelului/prompt-ului se face într-un singur loc
- **Testable**: Se poate benchmarka independent de sursă
- **Cost-tracked**: Consumul Gemini e vizibil per canal

---

## 2. Input Contract

Orice canal care apelează INSIGHT trebuie să furnizeze:

```json
{
  "content": "string — textul complet (obligatoriu)",
  "channel": "string — x-twitter|youtube|reddit|linkedin|newsletter|skool|github",
  "author": "string — numele/handle-ul autorului",
  "url": "string — URL original",
  "engagement": {
    "views": "number (opțional)",
    "likes": "number (opțional)",
    "bookmarks": "number (opțional)",
    "comments": "number (opțional)"
  },
  "engagement_score": "number — calculat de canalul sursă",
  "dedup_checked": "boolean — true dacă URL a trecut dedup gate (opțional)",
  "content_type": "string — tweet|article|video_transcript|thread|post|comment",
  "extracted_at": "ISO timestamp",
  "media": ["array of media URLs — opțional"]
}
```

### Engagement Score Normalization

- `engagement_score` este calculat de fiecare canal conform propriei formule.
- INSIGHT rutează pe baza valorii primite, nu pe formula.
- Threshold-ul Mode A (`>2000`) se aplică uniform pe scorul normalizat.
- Fiecare canal TREBUIE să documenteze formula în propria procedură de extracție.

---

## 3. Routing (Dual-Layer: Gemini Default + Opus High-Value)

### Arhitectura Dual-Layer

```
Post trece filter → Calculează engagement_score →
  IF engagement_score > 5000 OR manual_flag="opus":
    → Mode A-Deep (Opus) — verificare claims, entity discovery, bias detection
  ELIF engagement_score > 2000 OR content_type in [article, video_transcript]:
    → Mode A-Standard (Gemini Flash) — analiză rapidă, 10 secțiuni
  ELIF batch scan (top N):
    → Mode B (Gemini Flash) — batch overview
  ELSE:
    → Mode C — metrics-only store
```

**De ce dual-layer**: Gemini Flash e rapid ($0.00) dar superficial — acceptă toate claims-urile fără verificare, nu detectează sensaționalism, nu caută surse originale. Opus e lent (~90s) și costă (~$0.15-0.20/post) dar verifică claims real (caută paper-ul pe ArXiv), identifică autorii, detectează bias, și produce action items specifice cu IDs/DOIs.

**Buget Opus estimat**: ~3-5 posturi/săptămână × $0.20 = $0.60-$1.00/săptămână.

---

### Mode A-Standard: Gemini Flash (Default)
**Când**: `engagement_score > 2000` SAU `content_type in [article, video_transcript]`
**Tool**: Gemini 2.5 Flash (OAuth free) — `/opt/homebrew/bin/gemini -m gemini-2.5-flash`
**Cost**: $0.00 (1000 calls/day)
**Timp**: ~8s/post
**Calitate**: 6/10 — complet dar superficial, claims "verified within context" only

**Prompt Gemini (10 secțiuni)**:
```
Analyze this {content_type} from {channel} by @{author}.

Content:
---
{content}
---

Engagement: {views} views, {likes} likes, {bookmarks} bookmarks

Provide analysis in these 10 sections:

1. SUMMARY (2-3 sentences, what is this about)
2. KEY CLAIMS (bullet points, factual claims made)
3. COMPETITIVE INTELLIGENCE (companies, products, market moves mentioned)
4. MARKET SIGNALS (trends, shifts, opportunities, threats)
5. ENTITIES (people, companies, products, technologies, with context)
6. SENTIMENT (positive/negative/neutral, confidence 0-1)
7. RELEVANCE SCORE (1-10 for AI/SaaS/market intelligence/automation topics)
8. ACTION ITEMS (what should we do based on this intelligence)
9. FOLLOW-UP (questions to investigate, accounts to monitor, topics to track)
10. REFERENCED MATERIALS (books, research papers, courses, frameworks, tools, datasets explicitly mentioned or recommended in the content. For each: title, author if known, type: book|paper|course|framework|tool|dataset|report, and any URL or identifier mentioned. If none found, write "None detected.")

Be specific and actionable. Skip sections if truly not applicable.
```

**Post-Gemini upgrade check**:
```python
# După Gemini Mode A, verifică dacă merită upgrade la Opus
gemini_result = parse_gemini_output(raw_output)
relevance = gemini_result.get("relevance_score", 0)

if relevance >= 8 and engagement_score >= 5000:
    # Upgrade to Opus for deep verification
    opus_result = run_opus_insight(content, engagement)
    final_result = opus_result  # Opus replaces Gemini
    final_result["upgraded_from"] = "gemini"
```

---

### Mode A-Deep: Opus (High-Value Only)
**Când**: `engagement_score > 5000` SAU `manual_flag="opus"` SAU upgrade din Gemini (relevance ≥8 + engagement ≥5000)
**Tool**: Claude Opus 4.6 (via Genie subagent)
**Cost**: ~$0.15-$0.20/post
**Timp**: ~60-90s/post
**Calitate**: 9/10 — claims verification reală, entity discovery, bias detection, specific action items

**Prompt Opus (10 secțiuni + verificare)**:
```
You are running ECHELON INSIGHT Mode A-Deep analysis. Be rigorous, specific, and actionable.
This is for competitive intelligence purposes.

Analyze this {content_type} from {channel} by @{author}.

Content:
---
{content}
---

Engagement: {views} views, {likes} likes, {bookmarks} bookmarks

Provide analysis in these 10 sections:

1. SUMMARY (2-3 sentences)
2. KEY CLAIMS (bullet points, factual claims made)
3. KEY CLAIMS VERIFICATION (for each claim: verified/unverified/misleading, with brief reasoning.
   IMPORTANT: Do NOT just verify "within context of the article." Actually search for the original
   sources — papers on ArXiv, official announcements, author profiles. Flag sensationalized or
   embellished claims explicitly.)
4. COMPETITIVE INTELLIGENCE (companies, products, market moves — with specific implications)
5. MARKET SIGNALS (trends, shifts, opportunities, threats — be specific about why each matters)
6. ENTITIES (people, companies, products, technologies — discover real identities, not just what
   the post mentions. Find paper authors, company affiliations, DOIs.)
7. SENTIMENT (positive/negative/neutral, confidence 0-1. Note if the tone is sensationalized
   vs. the underlying source material's actual tone.)
8. RELEVANCE SCORE (1-10 for AI/SaaS/market intelligence/automation. Deduct points for
   missing actionability or excessive sensationalism.)
9. ACTION ITEMS (specific and actionable — include paper IDs, URLs, metrics to track.
   Not generic "monitor the space" but concrete next steps.)
10. REFERENCED MATERIALS (books, papers, courses, tools, datasets. For each: title, author,
    type, and identifier (ArXiv ID, DOI, ISBN, URL). Search for the actual source if the post
    only mentions it by name.)

Return structured analysis only.
```

**Diferențe cheie Opus vs Gemini**:
| Capabilitate | Gemini | Opus |
|-------------|--------|------|
| Claims verification | "within context" (lazy) | **Caută sursa originală** (ArXiv, DOI) |
| Entity discovery | Doar ce e în text | **Găsește autori reali, afilieri** |
| Bias/sensationalism | Nu detectează | **Flagează explicit** |
| Action items | Generice | **Specifice cu IDs, URLs, metrici** |
| Relevance scoring | Inflat (always 9-10) | **Realist, deduce puncte motivat** |
| Referenced materials | Titlu doar | **ArXiv ID, DOI, PMC links** |

---

###
