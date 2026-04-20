---
name: sentiment-analysis-ro
description: "Romanian-aware sentiment analysis workflow using local NLP pipeline and Claude-native fallback"
---

Romanian-aware sentiment analysis workflow using local NLP pipeline and Claude-native fallback

# Sentiment Analysis

## Purpose
Run consistent sentiment analysis for Romanian and English text, with optional entity extraction and Cortex storage.

## Local NLP Pipeline (Preferred for batch/repeat work)
Pipeline assets live in:
- `~/.openclaw/skills/sentiment-analysis/SKILL.md`
- `~/.openclaw/scripts/nlp/language-router.py`
- `~/.openclaw/scripts/nlp/romanian-sentiment.py`
- `~/.openclaw/scripts/nlp/entity-extract.py`
- venv: `~/.openclaw/scripts/nlp/.venv/`

### 1) Auto language routing sen
