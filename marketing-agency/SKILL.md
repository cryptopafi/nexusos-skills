---
name: marketing-agency
description: >
  Load full project context for the AI Marketing Agency project. Activates operational rules,
  technical decisions, business strategy, research references, and partnership intel.
  Use when the user says "marketing agency", "agency project", "lucram la agentie",
  "/marketing-agency", "continuam cu agentia", or any reference to working on the marketing
  agency business. Also trigger when discussing agency pricing, segments, tech stack decisions,
  or partner references (Luigi, AI.ANIMA, Leo's procedures).
---

# AI Marketing Agency — Project Context Loader

When this skill activates, you are now working on the **AI Marketing Agency** project.
Tag all work, Cortex stores, and file operations to this project.

## Project Location
- Project card: `/Users/pafi/.nexus/projects/ai-marketing-agency/PROJECT-CARD.md`
- Procedures: `/Users/pafi/.nexus/procedures/training/marketing-strategy/`
- LEO map: `/Users/pafi/.nexus/projects/ai-marketing-agency/LEO-PROCEDURES-MAP.md`
- Blueprint: search Cortex for "AI Marketing Agency Architectural Blueprint"

## Operational Rules

These rules come directly from Pafi and override defaults:

### 1. Delegation First
You are the orchestrator. ALWAYS delegate tasks to subagents. Stay available for Pafi.
Never do heavy work yourself — spawn agents for research, ingestion, audits, writing.

### 2. Model Routing for Subagents
Select model based on task complexity:
- **Opus**: architecture decisions, complex synthesis, INSIGHT reports
- **Sonnet**: research, content creation, tool comparison, scraping
- **Haiku**: signal detection, classification, lightweight data extraction

### 3. Save Everything
Every insight from every link Pafi sends must be saved to:
- **Cortex** (collection: "research", metadata: {project: "ai-marketing-agency"})
- **PROJECT-CARD** (cross-reference section)
- **Notion Intel Hub** (database: 327d31d1-1b7d-819a-972a-c10f82224289)
This applies regardless of topic — even if a link seems unrelated, store it.

### 3b. Backlink Everything to PROJECT-CARD
Every piece of work on this project MUST be backlinked to the PROJECT-CARD:
- New research → add Cortex ID + summary to PROJECT-CARD Research section
- New decisions → add to PROJECT-CARD Decisions section
- New partnerships → add to PROJECT-CARD Partnerships section
- New procedures → add to PROJECT-CARD Procedures section
Path: `/Users/pafi/.nexus/projects/ai-marketing-agency/PROJECT-CARD.md`

### 3c. Undecided Items → braindump
Decisions "in discussion" but NOT yet confirmed go to braindump, not PROJECT-CARD:
- Possible future tasks
- Ideas under consideration
- Items waiting for Leo's decision
- Options being evaluated
Path: `/Users/pafi/.nexus/projects/ai-marketing-agency/braindump.md`

### 3d. Notion DB Routing
Three databases, three purposes:
- **Intel Hub** (`327d31d1-1b7d-8129-b036-000b23f88829`) — LIVE MONITORING SOURCES ONLY: X accounts, YT channels, GitHub orgs, newsletters, blogs that update regularly. SourceChannel = account/channel URL (not individual post).
- **Content Inbox** (`326d31d1-1b7d-81bd-b9f1-000bdac0f30b`) — EXTRACTED CONTENT: insights from specific links, competitor analysis, article summaries, video takeaways. URL = the specific post/page.
- **Master Tasks** (`31bd31d1-1b7d-810d-a0cf-000beeddeee1`) — ACTION ITEMS: tasks to execute, deadlines, assignments.
- URL format: `https://www.notion.so/{id-without-hyphens}`
- Use `mcp__notion__API-post-page` to create pages, `mcp__notion__API-query-data-source` to query
- Link Notion page ID back in PROJECT-CARD for cross-reference
- Also available: Decisions Log (`31bd31d1-1b7d-8156`), Contacts (`31bd31d1-1b7d-8114`), Active Projects (`31cd31d1-1b7d-817e`)

### 3e. Intel Hub SourceChannel Rule
SourceChannel = the CHANNEL/ACCOUNT, not the individual post:
- X: `https://x.com/handle` (not the status URL)
- YouTube: `https://youtube.com/@channel` (not the video URL)
- GitHub: `https://github.com/org-or-user` (not the specific repo)
- Instagram: `https://instagram.com/handle`
- Website: root domain (e.g., `https://okara.ai`)
The individual post/video/repo URL goes in the URL field.

### 4. Research Tools (COST RULES)
- USE: `mcp__perplexity__search` (Sonar Pro) — primary research
- USE: Gemini Deep Research via Gemini CLI — for deep dives
- DO NOT USE: `mcp__perplexity__deep_research` — too expensive
- USE: `mcp__brave-search__brave_web_search`, `mcp__tavily__tavily_search` — supplementary
- USE: GitHub search, Apify actors — for tools/repos/social
- ALWAYS include GitHub/repos in research scope

### 5. Proactive Research
When new insights arrive, automatically command additional research if something seems missing.
Don't wait for Pafi to ask — identify gaps and fill them.

### 6. Leo Decides
The following decisions belong to Leo (co-founder, marketing guru):
- Brand name and personality
- Pricing (validated range: $149-$4,999/mo across segments)
- Product list and launch order
- Visual identity and design choices

### 7. Verification
Periodically check if background agents are blocked or zombie. Restart as needed.

## Business Decisions (CONFIRMED)

### Identity
- **Market**: Global + Romania + Italy
- **Timeline**: AGGRESSIVE — 30 days to first client
- **Co-founders**: Pafi + Leo + possibly Cody
- **Legal**: Delaware LLC (existing, keep) + Romania SRL (add, 1% CIT sub 100K EUR)
- **Budget**: Max $1,000/mo bootstrap, prefer build over buy
- **First clients**: Warm market
- **Partnership**: Luigi Emanuele Foscale / AI.ANIMA (ai-anima.ai)
  - Grownnectia = 1,400+ startups = biggest client pipeline
  - 14 businesses, serial entrepreneur, 46K IG followers

### Segments (ALL 4 from start)
1. **B2B** — Small ($199/mo) / Growth ($599/mo) / Enterprise ($1,999+/mo)
2. **B2C/KOL** — Creator ($149/mo) / KOL Pro ($399/mo) / KOL Enterprise ($999+/mo)
3. **B2P Political** — Local ($499/mo) / Regional ($1,499/mo) / National ($4,999+/mo)
4. **Products** — Standalone (AI Audit, Lead Finder, Content Waterfall, Brand Voice Kit, etc.)

### Pricing Gap (VALIDATED)
Target: **$499-$1,499/mo "intelligent execution" band**
- Below: SaaS tools $19-499 (commodity, shallow)
- Above: Agencies $2,500-$25K+ (premium, fully booked)
- Nobody does full-funnel autonomous execution at $500-1,500/mo

### Support Model
- **B2C**: AI complet (possibly via AI.ANIMA Digital Humans), human only if AI fails
- **B2B/Enterprise/B2P**: AI does filtering + lead prep, human takes over for close

## Technical Decisions (CONFIRMED)

### Architecture
- **Orchestration**: LangGraph (scored 82/90, #1 recommendation)
- **Frontend**: Next.js 16 + React 19 + Tailwind + shadcn/ui + Framer Motion
- **Backend**: FastAPI (Python, async-first)
- **AI Gateway**: LiteLLM or Portkey (multi-model routing + circuit breakers)
- **Database**: Supabase (PostgreSQL + RLS for multi-tenancy)
- **Vector DB**: Qdrant (separate instance from NexusOS)
- **Hosting**: Vercel (frontend) + Railway (backend) + Cloudflare (CDN)
- **Auth**: Clerk (fast MVP) or better-auth (ownership)
- **Payments**: Stripe Billing + Metronome (AI token metering)
- **CRM**: GoHighLevel hybrid — GHL for infrastructure + custom AI layer on top
- **Social Publishing**: Late/Zernio $49/mo unified API (NOT build direct)
- **Monitoring**: Langfuse + Helicone + Sentry + OpenTelemetry

### Multi-Model Routing (saves 50-70% costs)
- Claude Sonnet → copy, strategy, nuance
- Claude Opus → code generation, complex orchestration
- GPT-5.2 → structured JSON, math, function calling
- Gemini 3 Flash → bulk content (6-8x cheaper)
- Gemini 3 Pro → long docs (1M context)

### Agent Architecture (11 + orchestrator)
Each agent has: defined model, explicit boundaries (does NOT), signal tiering, error handling.
Content waterfall: Research → Strategy → Write → SEO/Social/Email → Analytics → Auto-Optimization.

## Research Cortex IDs (18 completed)

| ID | Topic | Tier |
|----|-------|------|
| R-01 `8cd25f9f` | Web Design Best Practices 2026 | T1 |
| R-02 `1f092b65` | AI Content Creation Tools | T1 |
| R-03 `6f48728e` | AI Video Creation Tools | T1 |
| R-04 `b401d233` | AI Ad Creation & Management | T1 |
| R-05 `dd34cdf9` | Multi-Agent Frameworks (LangGraph winner) | T1 |
| R-06 `f901debc` | Brand Voice AI (Qdrant, RAG+few-shot) | T1 |
| R-07 `36eb7a7d` | GoHighLevel Deep Dive (hybrid rec.) | T1 |
| R-08 `1410d2e6` | Tech Stack Best Practices | T2 |
| R-09 `04a9194c` | Incorporation Jurisdiction (DE+RO) | T2 |
| R-10 `00975592` | SEO + GEO/AEO Strategy | T2 |
| R-11 `c972ad4d` | Social Media APIs (Late/Zernio rec.) | T2 |
| R-12 `ab6c414a` | Email Marketing (ActiveCampaign+Postmark) | T2 |
| R-13 `ff13a041` | Analytics & Reporting (Cube.js+Tremor) | T2 |
| R-14 `5ab1c7b6` | Lead Generation (Clay+Hunter.io MCP) | T3 |
| R-15 `2a090acd` | AI Image Generation (6-tool stack) | T3 |
| R-16 `e9b42ec4` | Influencer Platforms (Modash+HypeAuditor) | T3 |
| R-17 `8303e20d` | Political Compliance RO/EU/US/IT | T3 |
| R-18 `7a20c403` | AI Voice & Podcast (ElevenLabs+Riverside) | T3 |

## Additional Intel Cortex IDs

| ID | Content |
|----|---------|
| `d0f555d7` | 50 AI agencies deep scrape + INSIGHT |
| `809cdde8` | AI.ANIMA full profile |
| `8fe595d5` | Luigi Foscale 14 businesses due diligence |
| `27960c1c` | Luigi partnership opportunity map |
| `0d9e1578` | ECHELON batch 1 synthesis (8 links) |
| `8373349a` | FameUp + Influee synthesis |
| `d4bcee32` | Revenue Experts AI (ekuzevska) |
| `2f789c99` | ECHELON batch 6 synthesis (AgencyFlo, Okara, CORD) |
| `8569b046` | ECHELON batch 3 synthesis (OpenCMO, AgencyOS) |
| `a7193b13` | 5-step agent orchestration framework (OpenClaw cross-ref) |
| `6021c055` | Adam Erhart agency startup playbook |
| `e071454f` | Session handoff 2026-03-18 (all decisions) |

## Key Competitive Insights

1. **GEO (Generative Engine Optimization) = new SEO** — track brand visibility in AI chatbots
2. **CORD governance** (ALLOW/CONTAIN/CHALLENGE/BLOCK) — best agent safety framework
3. **HAAO** — 88 agents per human (Moltbook/Meta benchmark)
4. **Single Grain FULLY BOOKED at $25K+/mo** — requires Claude Code for ALL staff
5. **Content waterfall** = universal pattern (Research→Strategy→Write→SEO→Social→Outreach)
6. **EU political ads: Meta/Google/TikTok EXITED** — only X remains
7. **Brand Voice Engine = #1 differentiator** — nobody does feedback loop + constitutional review

## Satellite View

```
ACUM ──> FUNDATIE ──> MVP ──> VALIDARE ──> SCALE ──> ENTERPRISE
 |         |           |        |            |          |
 0 cli.    0 cli.      5 cli.   50 cli.      200 cli.   1000 cli.
 $0        $0          $1K MRR  $15K MRR     $60K MRR   $300K MRR
 |         |           |        |            |          |
 Research  Brand+Web   B2B      +B2C/KOL     +Ads+SEO   +B2P+WL
 Design    Onboarding  Starter  +Growth      +Products  +Marketplace
 Agents    4 agents    Pipeline Full waterf. Full stack  Governance
```

## Remaining Questions for Leo
1. Brand name (generăm opțiuni, Leo alege)
2. Brand personality (dual-tone premium B2B + accessible B2C?)
3. Pricing final per segment/tier
4. Product list and launch order
5. Cody — co-founder da/nu?
