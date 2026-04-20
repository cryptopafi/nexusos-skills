---
name: sentiment-analysis
description: "NLP sentiment analysis via transformers venv"
---

NLP sentiment analysis via transformers venv

# Sentiment Analysis & NLP Pipeline

## When to Use
Analyze sentiment of Romanian or English text from any source (RSS, social media, reviews, articles).

## Commands

All scripts use a Python venv. Run directly (shebangs set) or via venv python:

### Sentiment Analysis (auto-detects language)
```bash
~/.openclaw/scripts/nlp/.venv/bin/python3 ~/.openclaw/scripts/nlp/language-router.py "Textul de analizat"
```
- Romanian → ro-sentiment model (84% accuracy, binary + neutral threshold)
- English → 
