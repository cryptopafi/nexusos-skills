---
name: gap-aware-search-protocol
description: Use when performing knowledge-gap-targeted search across ArXiv and other sources using ERRR method
---

Gap-Aware Search Protocol — MODULAR procedure for knowledge-gap-targeted search

Inspired by: ERRR (Extract-Refine-Retrieve-Read, ArXiv 2411.07820)
Applies at: WISH Step I (Investigate), after Cortex-first check

## When to use
- Cortex search returned results but score < 0.7 (partial knowledge)
- OR Cortex returned nothing but topic is not entirely new (we know adjacent things)
- NOT for simple lookups (L1) — only L2+

## Steps

### Step 1: EXTRACT — What do we already know?
After Cortex-first check, summarize in 2-3 bullets:
- What Cortex returned (even low-score results)
- What Genie knows from session context
- What adjacent knowledge exists (related procedures, past sessions)
Output: KNOWN_CONTEXT (max 200 words)

### Step 2: GAP — What is missing?
Explicitly articulate knowledge gaps:
- Compare KNOWN_CONTEXT against what the task needs
- List specific unknowns as questions
- Prioritize: which gaps block execution vs nice-to-have
Output: GAP_LIST (numbered, max 5 gaps)

### Step 3: REFINE — Target queries at gaps
For each gap in GAP_LIST:
- Formulate 1-2 search queries that specifically target that gap
- Assign optimal source per query (see Source Selection skill)
- Do NOT search for things we already know
Output: QUERY_PLAN (gap -> query -> source)

### Step 4: RETRIEVE — Execute targeted search
- Execute queries from QUERY_PLAN
- For each result, tag which gap it addresses
- Stop searching a gap once adequately covered

### Step 5: VERIFY — Did we fill the gaps?
- Check each gap: filled / partially filled / still open
- If critical gaps remain open: escalate search level (L2->L3)
- If all gaps filled: proceed to next WISH step

## Anti-patterns
- Searching broadly without articulating gaps first (old behavior)
- Re-searching topics where Cortex already has good coverage
- Ignoring low-score Cortex results that contain partial answers

## Integration
This replaces the ad-hoc search in WISH Step I. The Cortex-first check (existing) feeds into Step 1. Steps 2-5 are NEW.
