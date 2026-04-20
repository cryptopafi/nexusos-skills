---
name: eurostat-data
description: "EU statistical data from Eurostat API"
---

EU statistical data from Eurostat API

# Eurostat EU Statistics API

## When to Use
EU/Romanian economic statistics: GDP, inflation, energy prices, trade data.

## API
```bash
curl -s "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/DATASET?geo=RO&format=JSON"
```

## Key Datasets for Romania
| Dataset Code | Description |
|-------------|-------------|
| nrg_pc_204 | Electricity prices for household consumers |
| nrg_pc_205 | Electricity prices for non-household consumers |
| prc_hicp_manr | HICP inflation rate |

