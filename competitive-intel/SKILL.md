---
name: competitive-intel
description: "Structured competitor research via Exa + Reddit sentiment + HackerNews + Wikipedia"
---

Structured competitor research via Exa + Reddit sentiment + HackerNews + Wikipedia

# Competitive Intelligence

## 1. Competitive Intel Workflow

```text
Step 1: Cortex — avem deja research pe competitor?
Step 2: Wikipedia — profil general, history, funding
Step 3: Exa — "competitor [NAME] reviews pricing features 2026"
Step 4: Reddit JSON search — sentiment comunitate
   curl "https://www.reddit.com/search.json?q=[NAME]&sort=new&limit=25&t=month" \
     -H "User-Agent: genie-research/1.0"
Step 5: HackerNews Algolia — menții tech/startup
   curl "https://hn.algolia.com/api/v1/s
