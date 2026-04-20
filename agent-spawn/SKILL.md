---
name: agent-spawn
description: "Create high-signal subagent prompts with strict boundaries"
---

Create high-signal subagent prompts with strict boundaries

# Agent Spawn

## Purpose
Template standard de prompt pentru delegari Haiku, Sonnet sau Opus.

## Instructions
1. Construieste promptul in 5 sectiuni: `ROLE`, `INPUT`, `TASK`, `OUTPUT FORMAT`, `BOUNDARIES`.
2. `ROLE`: specialist clar + misiune unica.
3. `INPUT`: context taiat strict la ce e necesar.
4. `TASK`: 2-3 propozitii cu verbe concrete, rezultate masurabile.
5. `OUTPUT FORMAT`: structura + limita de lungime.
6. `BOUNDARIES`: ce NU face subagentul, fara preambul.
7. Respecta bugete context
