---
name: skill-library-consolidation
description: Use when consolidating scattered skills, plugins, and procedures into a unified searchable library
---

# Problema
Skills, plugins, procedures, prompts scattered across ~/.claude/skills/, ~/.agents/skills/, ~/.claude/plugins/, ~/.nexus/procedures/. No cross-agent searchability. OpenClaw and Hermes cannot access Claude CLI plugins natively.

# Procedura
Architecture: GitHub primary storage (4 new repos: nexusos-skills, nexusos-plugins, nexusos-prompts, hermes-backup) + Cortex semantic index (3 new collections: skills, prompts, plugins). 11 phases: P1 repo creation, P2 Cortex schema, P3 dedup 13 duplicate skills (auto-merge, compatible: frontmatter tag), P4 initial population, P5 Haiku summary generation (~$0.04), P6 Cortex indexing, P7 Hermes memory sync, P8 nightly sync script library-sync.sh at 03:00 MacM4, P9 VPS pull at 04:00, P10 plugin portability classification (9 simple→SKILL.md, 16 complex→OpenClaw Agent, 6 script-reuse), P11 verification. Plugin portability: simple plugins adapt to OpenClaw SKILL.md; complex plugins become dedicated OpenClaw Agents; bash scripts reused as-is.

# Enforcement Loop
4 manual decisions before build: (1) hermes-workspace rename vs new repo (2) review discovered/ prompts (3) confirm Hermes memories location (4) VPS Cortex decision. After decisions answered, dispatch TECH (Sonnet bypassPermissions) to build all 7 scripts.
