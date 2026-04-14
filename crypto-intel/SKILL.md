---
name: crypto-intel
description: Crypto asset due diligence and market analysis
triggers: ["/crypto-intel", "crypto analysis", "crypto due diligence"]
cli_tools: [~/.nexus/cli-tools/ccxt, ~/.nexus/cli-tools/dexscreener, ~/.nexus/cli-tools/feargreed, ~/.nexus/cli-tools/defillama, ~/.nexus/cli-tools/cryptopanic]
---

# Crypto Intel Skill

## Objective
Build a decision-grade due diligence report for a crypto asset, narrative, or sector.

## Workflow
1. Market structure:
- Pull spot/perp price, volume, and volatility.
- Pull funding rates and fear/greed context.
2. Liquidity and flow:
- Check DEX liquidity depth, spreads, and pool concentration.
- Track TVL/yields for protocol-level health signals.
3. Narrative and news:
- Pull CryptoPanic headlines and classify bullish/bearish catalysts.
4. Risk assessment:
- Detect red flags (low liquidity, high funding extremes, negative news clusters).
5. Synthesis:
- Produce concise risk matrix and directional bias.

## Output
- Thesis summary
- Market snapshot (price/volume/funding)
- Liquidity and on-chain proxy indicators
- News/sentiment summary
- Flags: `GREEN`, `YELLOW`, `RED`
- Confidence and monitoring triggers
