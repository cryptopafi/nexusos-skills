---
name: research-deep
description: Deep multi-domain research with synthesis
triggers: ["/research", "research deep", "investigate"]
mcps_required: [exa, tavily, brave-search, arxiv, pubmed-eutils, openalex]
---

# Research Deep Skill

## Objective
Execute ManuSearch-style deep research with planning, parallel search, and synthesis.

## 3-Agent Pattern
1. Planning agent:
- Decompose request into 3-5 sub-questions.
- Define evidence requirements and confidence thresholds.
2. Search agent:
- Run web search in parallel (Exa + Tavily + Brave).
- Run domain-specific retrieval in parallel (arXiv/OpenAlex/PubMed).
3. Synthesis agent:
- Merge findings, deduplicate, resolve contradictions.
- Return actionable summary with explicit confidence.

## Workflow
1. Parse user query and generate scoped research plan.
2. Launch parallel retrieval batches.
3. Extract facts with source URLs and publication timestamps.
4. Flag contradictory claims and gather additional evidence.
5. Produce final report and gap analysis.

## Output
- Executive summary (3 sentences)
- Key findings with citations
- Contradictions and unresolved questions
- Recommended reading list
- Confidence per finding (`HIGH`/`MEDIUM`/`LOW`)
