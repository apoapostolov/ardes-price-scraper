---
name: ardes-price-scraper
version: 1.0.0
description: |
  Search, scrape, and analyse PC component prices from Ardes.bg — Bulgaria's
  largest computer hardware retailer. Use when the user asks about current
  GPU, CPU, RAM, storage, or other PC part prices in Bulgaria; wants to find
  the cheapest option for a specific component; needs a price trend report;
  or wants to compare list vs promo prices across the catalogue.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# Ardes Price Scraper

## Overview

This skill drives an automated price-scraping tool that pulls live data from
the Ardes.bg configurator API, stores history in a local SQLite database, and
produces markdown price-change reports. The public repo lives at:

```
https://github.com/apoapostolov/ardes-price-scraper
```

Local install path (when deployed): the directory where the repo was cloned.

---

## Installation (autonomous — no user interaction required)

```bash
git clone https://github.com/apoapostolov/ardes-price-scraper.git
cd ardes-price-scraper
python -m venv venv
source venv/bin/activate          # Linux/macOS
# OR: venv\Scripts\Activate.ps1  # PowerShell
pip install -r requirements.txt
```

**Verify**:

```bash
cd src
python -m ardes_price_scraper.scraper --help
```

---

## Core Commands

All commands run from the `src/` directory inside the repo root.

### 1. Full scrape (collect all prices)

```bash
cd src
python -m ardes_price_scraper.scraper
```

- Fetches all category feeds from `ardes.bg`
- Writes a timestamped CSV to `output/ardes_prices_<timestamp>.csv`
- Appends new price rows to `data/ardes_prices.db` (7-day dedup guard)
- Generates a price-change markdown report in `output/price_changes_<timestamp>.md`

Run this to refresh data. The 7-day guard prevents duplicate insertions for
unchanged prices. Do not run more than once every 24 hours in normal usage.

### 2. Price-change report only (no scrape)

```bash
cd src
python -m ardes_price_scraper.report --write-latest --top 25
```

Use when data is already fresh and you only need the delta report.
Writes `output/price_changes_<timestamp>.md`.

Options:

```
--top N          Show top N price movers (default: 25)
--write-latest   Write output to file (required for file output)
```

### 3. Product search from latest CSV

```bash
cd src
python -m ardes_price_scraper.search_cli "<query>" --limit 10
python -m ardes_price_scraper.search_cli "<query>" --limit 10 --json
```

- Searches the latest CSV dump by normalised product name
- `--json` returns machine-readable output
- Use for quick lookups without querying the database

Examples:

```bash
python -m ardes_price_scraper.search_cli "rtx 4070" --limit 5
python -m ardes_price_scraper.search_cli "ryzen 5 7600" --limit 3 --json
python -m ardes_price_scraper.search_cli "ddr5 32gb" --limit 10
```

### 4. Database search API (most powerful)

```bash
cd src
python search_api.py "<query>" [--type "<category>"] [--manufacturer "<brand>"] [--max-price <BGN>] [--limit N]
```

- Queries `data/ardes_prices.db` directly for structured results with JSON output
- Supports manufacturer, category, subcategory, and price-range filters
- Best for AI consumption — returns structured JSON

Examples:

```bash
python search_api.py "rtx 4070" --limit 5
python search_api.py --manufacturer "NVIDIA" --max-price 1000
python search_api.py "DDR5" --type "Memory"
python search_api.py "rx 7600" --manufacturer "AMD" --limit 3
```

### 5. MCP wrapper (programmatic)

```bash
python mcp_wrapper.py scrape
python mcp_wrapper.py search "rtx 4070" 5
python mcp_wrapper.py report
```

Or from Python:

```python
import sys
sys.path.insert(0, "/path/to/ardes-price-scraper")
from mcp_wrapper import scrape_prices, search_products, generate_price_report

result = search_products("rtx 4070", limit=5)
print(result)
```

---

## Decision Rules

| User intent | Command to use |
| --- | --- |
| "What does X cost on Ardes?" | `search_cli` or `search_api.py` |
| "Find the cheapest GPU under 1000 BGN" | `search_api.py --max-price 1000` |
| "Show me price changes this week" | `report --write-latest` |
| "Refresh / scrape fresh data" | `scraper` |
| "Compare AMD vs NVIDIA cards" | `search_api.py` twice with `--manufacturer` |
| Programmatic AI tool integration | `mcp_wrapper.py` |

- **Prefer `search_api.py`** over `search_cli` when you need structured output or filters.
- **Only run the full scraper** when the user explicitly asks for fresh data or the
  latest CSV is older than 24 hours.
- **Never scrape more than once every few hours** — Ardes.bg throttles aggressive scrapers.

---

## Configuration

`config.toml` in the repo root controls behaviour:

```toml
[scraper]
output_dir = "../output"
database_path = "data/ardes_prices.db"
min_days_between_price_rows = 7     # dedup guard
subcat_scan_min = 1
subcat_scan_max = 100
allowed_subcats = [19, 20, 21, 23, 24, 37, 48, 191]
```

Key subcategory IDs for common searches:

| Subcategory | ID |
| --- | --- |
| RAM / Memory | 19 |
| CPU | 20 |
| Motherboard | 21 |
| PSU | 23 |
| PC Cases | 24 |
| GPU | 37 |
| Thermal Paste | 48 |

To scrape a single category, edit `allowed_subcats` to contain only that ID.

---

## Output Files

All outputs land in `src/output/`:

| File | Contents |
| --- | --- |
| `ardes_prices_<timestamp>.csv` | Full price snapshot (all scraped products) |
| `price_changes_<timestamp>.md` | Top movers, new products, removed products |

Database: `src/data/ardes_prices.db` — SQLite, two tables:

- `products`: slug, normalised name, first_seen
- `price_history`: product_ref, recorded_at, price_bgn, deal_price_bgn, price_eur

---

## AI Analysis (optional)

The scraper integrates with OpenRouter for market analysis in the price
report. Set `OPENROUTER_API_KEY` in the environment before running the
full scraper if AI commentary is wanted:

```bash
export OPENROUTER_API_KEY="sk-or-..."
cd src
python -m ardes_price_scraper.scraper
```

Without the key, scraping and reports work fully — only the AI narrative
summary in the markdown report is skipped.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `FileNotFoundError: No CSV files found` | Run the full scraper first |
| `Database not found` | Run from the `src/` directory |
| Empty search results | Check spelling; run scraper to refresh data |
| Report shows no changes | Data is within the 7-day dedup window |
| Scraper returns 0 products | Ardes.bg may be throttling — wait and retry |
