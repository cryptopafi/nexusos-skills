# Deep Research Skill (199-bio)
# Source: https://github.com/199-biotechnologies/claude-deep-research-skill
# Security audit: PASSED 2026-02-24 (Genie)
# Install date: 2026-02-24

## Trigger
When user says: "deep research [TOPIC]", "comprehensive research", "research [TOPIC] mode=deep/standard/quick"

## Core Purpose
Enterprise-grade research via 8-phase pipeline: Scope → Plan → Retrieve → Triangulate → Synthesize → Critique → Refine → Package.
Delivers citation-backed reports with source credibility scoring.

## Decision Framework
**Skip if**: Simple lookup, debugging, answerable with 1-2 searches.
**Proceed if**: Complex analysis requiring 10+ sources, verified claims, multi-perspective comparison.

## Execution Modes
- **Quick** (2-5 min): Exploration, broad overview
- **Standard** (5-10 min): Most use cases [DEFAULT]
- **Deep** (10-20 min): Important decisions
- **UltraDeep** (20-45 min): Critical analysis, maximum rigor

## CRITICAL: Parallel Execution
Launch 5-10 independent searches SIMULTANEOUSLY in a single message with multiple tool calls — NEVER sequential.
Spawn 3-5 parallel agents for deep investigation phases.

## Anti-Hallucination Requirements
- Every factual claim must cite source immediately [N]
- Distinguish facts (from sources) vs synthesis (analysis)
- Use explicit markers: "According to [1]..." or "[1] reports..."
- Mark inferences as analysis, not fact
- Admit when sources unavailable — NEVER fabricate citations

## Report Delivery Standards

**Folder structure**: `~/Documents/[TopicName]_Research_[YYYYMMDD]/`

**Generate 3 formats**:
1. Markdown — Full detailed report with all findings
2. HTML — McKinsey-style template (navy #003d5c, gray #f8f9fa, compact layout)
3. PDF — Professional formatting with headers, page numbers

**Content requirements**:
- Minimum 2,000 words (standard mode)
- 10+ sources with complete bibliography
- Each major finding: 300-500 words with citations
- 80%+ prose (not bullets) — bullets only for distinct lists
- Specific data, statistics, dates embedded in sentences
- Executive summary: 50-250 words

**Bibliography (ZERO TOLERANCE)**:
- Include EVERY citation [N] used in report body
- Format: [N] Author/Org (Year). "Title". Publication. URL
- NO placeholders, ranges, or truncation — write ALL entries individually
- Complete bibliography is non-negotiable

## Writing Standards
- **Precision**: "Mortality decreased 23% (p<0.01)" not "significantly improved"
- **Economy**: No fluff, no unnecessary modifiers
- **Directness**: State findings clearly with specific evidence
- **Source grounding**: "Smith et al. (2024) found..." [1] not vague "studies show"

## Progressive File Assembly (Unlimited Length)
Generate sections individually to file using Write/Edit tools.
Token limit: 32,000 tokens (~24,000 words) per execution.

**For reports >20,000 words**:
1. Generate Part 1 (sections 1-6) under 18K words
2. Save continuation state file with context preservation
3. Spawn continuation agent via Task tool
4. Chain continues recursively until complete

## Validation Gates
**Step 1**: Citation verification (DOI resolution, title matching, flags suspicious entries)
**Step 2**: Structure validation (exec summary length, required sections, citation format, bibliography completeness, word count, 10+ sources)
If fails: Fix up to 2 times, then report issues to user.

## Quality Minimums (Enforced)
- 10+ sources (document if fewer available)
- 3+ sources per major claim
- Limitations section mandatory
- Methodology documented
- Zero placeholder text

## Tool Stack (MCP required)
- Exa AI MCP — semantic search
- Wikipedia MCP — fact anchoring
- arXiv MCP — academic papers
- DuckDuckGo MCP — backup search
- fetch MCP — direct URL retrieval
- Cortex — prior research recall

## Autonomy Principle
Operate independently, infer assumptions from query context.
Request clarification ONLY if query is incomprehensible or contradictory.
Default to standard mode. Proceed without approval.
