---
name: deep-research
description: "Multi-source research orchestration with FAST/STANDARD/DEEP modes and anti-hallucination protocol"
---

Multi-source research orchestration with FAST/STANDARD/DEEP modes and anti-hallucination protocol

# Deep Research

## 1. Tool Routing Table

```text
QUERY TYPE                  → PRIMARY TOOL              → FALLBACK
────────────────────────────────────────────────────────────────────
Quick factual lookup        → wikipedia MCP             → fetch MCP
Current news/events         → exa MCP                   → brave-search MCP
Academic/technical          → arxiv MCP                 → fetch (Semantic Scholar)
Semantic/conceptual search  → exa MCP                   → tavily MCP
Agent-optimized re
