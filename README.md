# Ardes Price Scraper

A Python tool to scrape and track PC component prices from Ardes.bg, Bulgaria's leading computer hardware retailer. Automatically collects pricing data, generates price change reports, and provides search capabilities for efficient price lookups.

## AI Installation Instructions (OpenClaw)

**For autonomous AI installation without user interaction:**

```bash
# Clone repository
git clone https://github.com/apoapostolov/ardes-price-scraper.git
cd ardes-price-scraper

# Set up Python environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# OR: venv\Scripts\activate  # Windows PowerShell
# OR: venv\Scripts\activate.bat  # Windows CMD

# Install dependencies
pip install -r requirements.txt

# Run initial price scrape
python -m ardes_price_scraper.scraper

# For MCP integration, use the wrapper
python mcp_wrapper.py scrape
```

**MCP Functions Available:**
- `scrape_prices()`: Run full price scraping
- `search_products(query, limit=5)`: Search database for products
- `generate_price_report()`: Create price change analysis

## Features

- **Comprehensive Price Scraping**: Fetches all product prices from Ardes.bg configurator feeds
- **Price History Tracking**: Stores historical pricing data in a SQLite database with deduplication
- **Price Change Analysis**: Generates detailed markdown reports highlighting price movements
- **Product Search**: Fast search API for finding products by name, manufacturer, or category
- **CSV Export**: Timestamped CSV exports for data analysis
- **Configurable**: TOML-based configuration for output directories, database paths, and update intervals

## Requirements

- Python 3.11+
- Internet connection for scraping

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ardes-price-scraper.git
   cd ardes-price-scraper
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Scraping

Run the scraper to fetch current prices and generate reports:

```bash
cd src
python -m ardes_price_scraper.scraper
```

This will:
- Download all product feeds from Ardes.bg
- Save a timestamped CSV file in `output/`
- Update the SQLite database with new prices
- Generate a price change report

### Search Products

Search for specific products:

```bash
cd src
python search_api.py "rtx 4070" --limit 5
```

Or use the command-line search:

```bash
python -m ardes_price_scraper.search_cli "rx 7600" --limit 10
```

### Generate Price Reports

Create price change analysis reports:

```bash
cd src
python -m ardes_price_scraper.report --write-latest --top 25
```

## Configuration

Edit `config.toml` to customize:
- Output directory paths
- Database file location
- Update intervals for price deduplication

## Windows Quick Start

Double-click `run_scraper.bat` to run the scraper with default settings.

## Linux/macOS Quick Start

Make the script executable and run it:

```bash
chmod +x run_scraper.sh
./run_scraper.sh
```

## PowerShell Quick Start

Run the PowerShell script:

```powershell
.\run_scraper.ps1
```

## Testing

Run the test suite:

```bash
pytest
```

Or using the Makefile (Linux/macOS):

```bash
make test
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please open issues for bugs or feature requests.