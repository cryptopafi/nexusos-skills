---
name: search-flights-browser
description: AI-driven flight search fallback using agent-browser. Use when Playwright MCP scrapers are blocked or unavailable. Navigates Google Flights (with Kayak fallback), extracts flight results via AI page reading (no CSS selectors), and returns structured JSON matching the Travel Agent flight schema. Triggers include "search flights browser", "browser flight search", "google flights fallback", or when the travel agent pipeline needs a browser-based flight source.
argument-hint: <origin_iata> <dest_iata> <date YYYY-MM-DD> [currency] [max_results]
---

# /search-flights-browser — AI Browser-Based Flight Search

Fallback flight search using agent-browser when API-based MCPs are unavailable or blocked. Navigates Google Flights, reads results intelligently (no fragile CSS selectors), and returns structured JSON.

## Arguments

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `origin_iata` | Yes | — | Origin airport IATA code (e.g. `OTP`) |
| `dest_iata` | Yes | — | Destination airport IATA code (e.g. `LHR`) |
| `date` | Yes | — | Departure date in `YYYY-MM-DD` format |
| `currency` | No | `EUR` | Currency for prices |
| `max_results` | No | `5` | Maximum number of flights to return |

## Output Schema

Always return results in this exact structure, even if partial:

```json
{
  "flights": [
    {
      "airline": "British Airways",
      "price": 316,
      "duration_minutes": 225,
      "stops": 0,
      "departure_time": "08:15",
      "arrival_time": "10:00",
      "link": "https://www.google.com/travel/flights/...",
      "source": "agent-browser-google-flights"
    }
  ],
  "source": "agent-browser-google-flights",
  "total_found": 3
}
```

If no results are found, return:
```json
{"flights": [], "source": "agent-browser-google-flights", "total_found": 0, "error": "<reason>"}
```

---

## Execution Steps

### Step 1: Prepare Inputs

Resolve full airport names for search fields (Google Flights requires human-readable names, not IATA codes):
- Use the IATA code to derive a commonly known airport name, e.g.:
  - `OTP` → `"Bucharest OTP"`
  - `LHR` → `"London LHR"`
  - `CDG` → `"Paris CDG"`
  - `JFK` → `"New York JFK"`
- Format date as displayed in Google Flights: `YYYY-MM-DD` is accepted as-is in the URL.

### Step 2: Navigate to Google Flights

Use the agent-browser skill to open Google Flights:

```
Task for agent-browser: "Navigate to https://www.google.com/travel/flights and wait for the page to fully load (network idle)."
```

Alternatively, use the direct URL format to pre-fill fields and skip form interaction:

```
https://www.google.com/travel/flights/search?tfs=CBwQAhoeEgoyMDI1LTEyLTMwagcIARIDT1RQcgcIARIDTEhS&hl=en&curr=EUR
```

Preferred approach: Use the **pre-filled URL** with IATA codes embedded. Construct it as:

```
https://www.google.com/travel/flights#flt={ORIGIN}.{DEST}.{DATE};c:{CURRENCY};e:1;s:0*1;sd:1;t:f
```

Example for OTP→LHR on 2025-12-30 in EUR:
```
https://www.google.com/travel/flights#flt=OTP.LHR.2025-12-30;c:EUR;e:1;s:0*1;sd:1;t:f
```

### Step 3: Fill Search Form (if pre-filled URL did not load results)

If results are not visible after loading the pre-filled URL, use agent-browser to fill in the form manually:

```
Task for agent-browser: "On https://www.google.com/travel/flights:
1. Clear the origin field and type '{ORIGIN_FULL_NAME}' (e.g. 'Bucharest OTP')
2. Clear the destination field and type '{DEST_FULL_NAME}' (e.g. 'London LHR')
3. Set the trip type to 'One way'
4. Set the date to '{date}' (format: Mon, Dec 30)
5. Ensure passengers = 1 adult
6. Click the Search button
7. Wait for results to load (network idle)"
```

### Step 4: Wait for Results

After navigation or search submission:

```
Task for agent-browser: "Wait for flight result cards to appear on the page. Wait up to 15 seconds for network idle. Then take a full-page screenshot to confirm results are visible."
```

### Step 5: Extract Flight Data (AI Page Reading)

This is the key step — use agent-browser to get the page text, then parse it as an AI, **without relying on CSS selectors**:

```
Task for agent-browser: "Get the full text content of the current page (agent-browser get text body). Return the raw text so I can extract flight information from it."
```

Once the page text is retrieved, parse it yourself as Claude:
- Identify each flight card / row in the text output
- Extract for each flight:
  - **Airline name** (e.g. "Wizz Air", "TAROM", "Ryanair")
  - **Price** as a number in the specified currency (strip currency symbols)
  - **Duration** — convert "Xh Ym" or "X hr Y min" to total minutes
  - **Stops** — "Nonstop" = 0, "1 stop" = 1, "2 stops" = 2
  - **Departure time** — HH:MM format (24h)
  - **Arrival time** — HH:MM format (24h)
  - **Link** — use current page URL if individual booking links are not extractable

Return up to `max_results` flights, sorted by price ascending.

### Step 6: Build and Return JSON

Construct the output JSON and return it to the caller:

```json
{
  "flights": [
    {
      "airline": "...",
      "price": 123,
      "duration_minutes": 180,
      "stops": 0,
      "departure_time": "06:30",
      "arrival_time": "08:10",
      "link": "https://www.google.com/travel/flights/...",
      "source": "agent-browser-google-flights"
    }
  ],
  "source": "agent-browser-google-flights",
  "total_found": N
}
```

---

## Fallback: Kayak

If Google Flights is blocked (CAPTCHA, empty results, or navigation fails after 2 attempts), switch to Kayak:

```
Task for agent-browser: "Navigate to https://www.kayak.com/flights/{ORIGIN}-{DEST}/{date} and wait for results to load. Then get the full text content of the page."
```

Example URL for OTP→LHR on 2025-12-30:
```
https://www.kayak.com/flights/OTP-LHR/2025-12-30
```

Apply the same AI text-extraction logic (Step 5) to parse Kayak results.
Update `source` field to `"agent-browser-kayak"` in the output JSON.

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Google Flights CAPTCHA / blank results | Switch to Kayak fallback immediately |
| Kayak also blocked | Return `{"flights": [], "error": "Both Google Flights and Kayak blocked by anti-bot", "source": "agent-browser-google-flights", "total_found": 0}` |
| Page loads but no flight cards found | Wait 5 more seconds, re-snapshot; if still empty, try Kayak |
| Partial results (fewer than max_results) | Return what was found; set `total_found` to actual count |
| Price is in wrong currency | Note in the flight object: `"price_currency": "USD"` alongside the numeric price |
| Date in the past | Return error: `{"error": "Date is in the past: {date}"}` |

---

## Usage Examples

```
/search-flights-browser OTP LHR 2025-12-30
/search-flights-browser OTP LHR 2025-12-30 EUR 10
/search-flights-browser BUH LGW 2026-01-15 USD 3
```

## Integration Note

This skill is designed as a **fallback layer** in the NexusOS Travel Agent pipeline (`~/.nexus/procedures/TRAVEL-AGENT.md`). It should be invoked after Kiwi MCP and Google Flights MCP have been tried and failed or returned no results. The output schema is intentionally identical to the Travel Agent flight schema so results can be merged without transformation.

Priority order in Travel Agent:
1. Kiwi MCP (API — preferred)
2. Google Flights MCP (API — preferred)
3. **This skill** (browser fallback — use when APIs blocked/down)
