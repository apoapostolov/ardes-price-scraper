# Ardes Price Scraper

A Python command-line tool for collecting PC hardware prices from Ardes.bg,
keeping local history in SQLite, searching snapshots, and producing Markdown
price-change reports.

## Requirements

- Python 3.11+
- Internet access for a fresh scrape

## Install

```bash
git clone https://github.com/apoapostolov/ardes-price-scraper.git
cd ardes-price-scraper
python -m venv .venv
```

Activate the environment and install dependencies:

Linux or macOS:

```bash
source .venv/bin/activate
```

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Then install the dependencies:

```bash
pip install -r requirements.txt
```

## Capabilities

- **Collect current catalogue prices.** The scraper reads the configured Ardes
  configurator subcategories and records list, deal, and euro prices.
- **Keep price history locally.** SQLite stores products and timestamped price
  rows with a configurable minimum interval between unchanged entries.
- **Export each scrape.** Every run writes a timestamped CSV snapshot for later
  search or comparison.
- **Find products quickly.** Search the latest CSV by words and category, or
  query the SQLite database with manufacturer, category, subcategory, and price
  filters.
- **Compare snapshots.** The report command identifies price increases,
  decreases, additions, and removals between two CSV files.
- **Generate a scrape-time market report.** The full scraper writes Markdown
  trend data and can request an OpenRouter analysis when an API key is present.

## Run a Scrape

The launchers activate `.venv` when present, change into `src/`, and run the
scraper:

```powershell
.\run_scraper.ps1
```

```bash
./run_scraper.sh
```

Or run it directly from `src/`:

```bash
cd src
python -m ardes_price_scraper.scraper
```

With the checked-in configuration, output is written to the repository's
`output/` directory and history is stored in `src/data/ardes_prices.db`.

## Search

Search the latest CSV snapshot:

```bash
cd src
python -m ardes_price_scraper.search_cli "rx 7600" --limit 10
python -m ardes_price_scraper.search_cli "ddr5 32gb" --json
```

Query the SQLite database for structured JSON:

```bash
cd src
python search_api.py "rtx 4070" --limit 5
python search_api.py --manufacturer NVIDIA --max-price 1000
python search_api.py "DDR5" --category "Memory (RAM)"
```

The database search response contains the effective filters, matching products,
and database metadata. An empty database returns an empty `results` array rather
than live catalogue data; run a scrape to populate it.

## Compare Existing Snapshots

The standalone report command needs two CSV snapshots:

```bash
cd src
python -m ardes_price_scraper.report --output-dir ../output \
  --write-latest --top 25
```

## Configuration

Edit [config.toml](config.toml) to control:

- allowed Ardes subcategories and display names
- CSV output and SQLite database paths
- unchanged-price deduplication interval
- request timeout, retry count, backoff, user agent, and optional proxy

The checked-in configuration enables selected PC component subcategories and a
seven-day minimum between unchanged price rows.

## Agent Integration

[`skills/ARDES_SCRAPER_SKILL.md`](skills/ARDES_SCRAPER_SKILL.md) routes agent
requests to the scraper, CSV search, database search, and report commands.

[`mcp_wrapper.py`](mcp_wrapper.py) is a local command wrapper. It does not run
as a standalone MCP server. Its `scrape` and `report` paths call the Python entry points; its
`search` function currently returns placeholder text and should not be used as
proof of a product lookup.

## Test

```bash
pytest
```

The current tests cover normalization and CSV report-delta behavior.

## Release and License Status

[CHANGELOG.md](CHANGELOG.md) records the initial `1.0.0` release dated
2026-03-28.

No `LICENSE` file is present in this repository. Do not assume the project is
MIT-licensed until a license is added.
