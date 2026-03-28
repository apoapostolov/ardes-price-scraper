from __future__ import annotations

import csv
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable, Dict, List, Tuple
import os
# Load repository root .env (if present) so environment variables set in the
# workspace root `.env` (e.g. OPENROUTER_API_KEY) are available to the scraper.
# This prefers repo-wide configuration over per-project .env files.
try:
    from dotenv import load_dotenv
    from pathlib import Path as _Path
    _repo_root = _Path(__file__).resolve().parents[4]
    _env_path = _repo_root / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except Exception:
    # dotenv is optional; fall back to process environment variables
    pass

from .categories import extract_descriptors
from .client import build_session, fetch_configurator_markup, iter_subcategory_products
from .config import ScraperConfig
from .db import PriceDatabase
from .normalization import ProductRecord, normalize_name, slugify_name

LOGGER = logging.getLogger(__name__)


def parse_price(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.replace("\u00a0", " ").replace(" ", "").replace(",", ".").strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def harvest_products(config: ScraperConfig) -> tuple[list[ProductRecord], dict[int, str]]:
    # Hardcoded descriptors based on ARDES_CATEGORIES.md
    descriptors = {
        8: "(unknown)",
        9: "(unknown)",
        10: "Монитор повече информация",
        12: "Принтер повече информация",
        13: "(unknown)",
        14: "(unknown)",
        15: "(unknown)",
        16: "(unknown)",
        17: "Външен твърд диск повече информация",
        18: "DVD / Външно повече информация",
        19: "2-ра памет (RAM) повече информация *Моля, изберете дънна платка, преди да изберете памет.",
        20: "Процесор (CPU) повече информация",
        21: "Дънна платка повече информация *Избраните дънна платка и кутия са несъвместими!",
        22: "(unknown)",
        23: "Захранване повече информация",
        24: "(unknown)",
        25: "Операционна система повече информация",
        28: "Офис приложения повече информация",
        29: "Антивирусен софтуер повече информация",
        30: "Клавиатура повече информация",
        31: "Мишка повече информация",
        34: "(unknown)",
        35: "(unknown)",
        36: "(unknown)",
        37: "2-ра видео карта (GPU) повече информация",
        47: "(unknown)",
        48: "Специална Термо паста за процесора повече информация",
        58: "(unknown)",
        62: "(unknown)",
        65: "(unknown)",
        69: "(unknown)",
        72: "МФУ повече информация",
        77: "(unknown)",
        78: "Озвучителна система повече информация",
        79: "(unknown)",
        81: "(unknown)",
        84: "(unknown)",
        88: "(unknown)",
        89: "(unknown)",
        90: "(unknown)",
        92: "(unknown)",
        191: "(unknown)",  # Assuming from config
    }

    # Create Selenium driver for session establishment
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    options = Options()
    # options.add_argument("--headless")  # Remove headless to run with UI
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Hide automation indicators
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    session = build_session(config)
    try:
        # Establish session with Selenium
        driver.get("https://ardes.bg")
        time.sleep(2)
        driver.get(config.base_url)
        # Allow manual Cloudflare/captcha confirmation before scraping cookies
        LOGGER.info("If Cloudflare shows a human verification prompt, solve it now; press Enter here when done...")
        try:
            input()
        except EOFError:
            time.sleep(10)

        # Get cookies from browser and set in session
        cookies = driver.get_cookies()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'))

        subcat_ids = sorted(descriptors.keys())
        if config.allowed_subcats:
            subcat_ids = [sid for sid in subcat_ids if sid in config.allowed_subcats]
        data = iter_subcategory_products(driver, config, subcat_ids)
    finally:
        driver.quit()
        session.close()

    records: list[ProductRecord] = []
    for subcat_id, items in data.items():
        # Use canonical English name from config, fallback to cleaned Bulgarian descriptor
        canonical_name = config.category_names.get(str(subcat_id))
        if canonical_name:
            descriptor = canonical_name
        else:
            descriptor = descriptors.get(subcat_id, "(unknown)")
            descriptor = descriptor.replace(" повече информация", "").strip()
            # Additional descriptor normalizations
            descriptor_replacements = {
                "2-ра памет (RAM) *Моля, изберете дънна платка, преди да изберете памет.": "Памет (RAM)",
                "Дънна платка *Избраните дънна платка и кутия са несъвместими!": "Дънна платка",
                "2-ра видео карта (GPU)": "Видео карта (GPU)",
            }
            for old, new in descriptor_replacements.items():
                descriptor = descriptor.replace(old, new)
        for item in items:
            title_raw = (item.get("title") or item.get("value") or "").strip()
            if not title_raw:
                continue
            price_bgn = parse_price(item.get("price"))
            deal_price = parse_price(item.get("d_price"))
            price_eur = parse_price(item.get("price_eur"))
            if price_bgn is None and deal_price is None:
                continue
            price_bgn = price_bgn or deal_price or 0.0
            record = ProductRecord(
                subcategory_id=subcat_id,
                descriptor=descriptor,
                title=title_raw,
                normalized_name=normalize_name(title_raw),
                slug=slugify_name(title_raw),
                product_id=str(item.get("product_id") or ""),
                price_bgn=price_bgn,
                deal_price_bgn=deal_price,
                price_eur=price_eur,
            )
            records.append(record)
    return records, descriptors


def write_csv(records: Iterable[ProductRecord], output_dir: Path, timestamp: datetime) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"ardes_prices_{timestamp.strftime('%Y%m%d_%H%M%S')}.csv"
    path = output_dir / filename
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "canonical_id",
                "subcategory_id",
                "descriptor",
                "product_id",
                "raw_name",
                "normalized_name",
                "slug",
                "price_bgn",
                "deal_price_bgn",
                "price_eur",
            ]
        )
        for record in records:
            writer.writerow(
                [
                    "",
                    record.subcategory_id,
                    record.descriptor,
                    record.product_id,
                    record.title,
                    record.normalized_name,
                    record.slug,
                    f"{record.price_bgn:.2f}",
                    f"{record.deal_price_bgn:.2f}" if record.deal_price_bgn is not None else "",
                    f"{record.price_eur:.2f}" if record.price_eur is not None else "",
                ]
            )
    return path


def update_csv_with_ids(path: Path, canonical_ids: list[int]) -> None:
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    header, data_rows = rows[0], rows[1:]
    for row, canonical_id in zip(data_rows, canonical_ids, strict=False):
        row[0] = str(canonical_id)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(data_rows)


def analyze_price_changes(db: PriceDatabase, days_back: int = 30) -> Dict[str, List[Tuple[str, float, float, float]]]:
    """Analyze price changes over the last N days.

    Returns a dict with keys 'decreases', 'increases', 'new_products' containing
    lists of (product_name, old_price, new_price, change_percent) tuples.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    cursor = db._conn.cursor()
    cursor.execute("""
        SELECT
            p.normalized_name,
            ph1.price_bgn as old_price,
            ph2.price_bgn as new_price,
            ph1.recorded_at as old_date,
            ph2.recorded_at as new_date
        FROM products p
        JOIN price_history ph1 ON p.id = ph1.product_ref
        JOIN price_history ph2 ON p.id = ph2.product_ref
        WHERE ph1.recorded_at < ph2.recorded_at
        AND ph2.recorded_at >= ?
        AND ph1.price_bgn IS NOT NULL
        AND ph2.price_bgn IS NOT NULL
        AND ph1.recorded_at = (
            SELECT MAX(recorded_at)
            FROM price_history ph3
            WHERE ph3.product_ref = p.id
            AND ph3.recorded_at < ph2.recorded_at
        )
    """, (cutoff_date.isoformat(),))

    changes = {'decreases': [], 'increases': [], 'new_products': []}

    for row in cursor.fetchall():
        name = row[0]
        old_price = row[1]
        new_price = row[2]

        if old_price > 0:
            change_percent = ((new_price - old_price) / old_price) * 100
            change_data = (name, old_price, new_price, change_percent)

            if change_percent < -5:  # Price decrease > 5%
                changes['decreases'].append(change_data)
            elif change_percent > 5:  # Price increase > 5%
                changes['increases'].append(change_data)

    # Find new products (products that appeared in the last scrape)
    cursor.execute("""
        SELECT p.normalized_name, ph.price_bgn
        FROM products p
        JOIN price_history ph ON p.id = ph.product_ref
        WHERE ph.recorded_at >= ?
        AND p.first_seen >= ?
    """, (cutoff_date.isoformat(), cutoff_date.isoformat()))

    for row in cursor.fetchall():
        changes['new_products'].append((row[0], 0, row[1], 0))

    # Sort by absolute change percentage
    changes['decreases'].sort(key=lambda x: x[3])  # Most decreased first
    changes['increases'].sort(key=lambda x: x[3], reverse=True)  # Most increased first

    return changes


def analyze_price_trends(db: PriceDatabase) -> Dict[str, Dict]:
    """Analyze price trends across multiple time periods for market analysis.

    Returns trend data for 14, 30, 90, and 180 days including:
    - Average price change percentages
    - Number of products with significant changes
    - Category-level trends
    - Market direction indicators
    """
    periods = [14, 30, 90, 180]
    trends = {}

    cursor = db._conn.cursor()

    for days in periods:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Get all price changes for this period
        cursor.execute("""
            SELECT
                p.normalized_name,
                ph1.price_bgn as old_price,
                ph2.price_bgn as new_price,
                ph1.recorded_at as old_date,
                ph2.recorded_at as new_date
            FROM products p
            JOIN price_history ph1 ON p.id = ph1.product_ref
            JOIN price_history ph2 ON p.id = ph2.product_ref
            WHERE ph1.recorded_at < ph2.recorded_at
            AND ph2.recorded_at >= ?
            AND ph1.price_bgn IS NOT NULL
            AND ph2.price_bgn IS NOT NULL
            AND ph1.recorded_at = (
                SELECT MAX(recorded_at)
                FROM price_history ph3
                WHERE ph3.product_ref = p.id
                AND ph3.recorded_at < ph2.recorded_at
            )
        """, (cutoff_date.isoformat(),))

        changes = []
        for row in cursor.fetchall():
            name = row[0]
            old_price = row[1]
            new_price = row[2]

            if old_price > 0:
                change_percent = ((new_price - old_price) / old_price) * 100
                changes.append({
                    'name': name,
                    'old_price': old_price,
                    'new_price': new_price,
                    'change_percent': change_percent,
                    'change_type': 'decrease' if change_percent < -5 else 'increase' if change_percent > 5 else 'stable'
                })

        # Calculate trend statistics
        significant_changes = [c for c in changes if abs(c['change_percent']) > 5]
        avg_change = sum(c['change_percent'] for c in changes) / len(changes) if changes else 0
        volatility = sum(abs(c['change_percent']) for c in changes) / len(changes) if changes else 0

        # Count by change type
        decreases = len([c for c in significant_changes if c['change_type'] == 'decrease'])
        increases = len([c for c in significant_changes if c['change_type'] == 'increase'])

        trends[f'{days}d'] = {
            'total_products': len(changes),
            'significant_changes': len(significant_changes),
            'decreases': decreases,
            'increases': increases,
            'avg_change_pct': avg_change,
            'volatility': volatility,
            'market_direction': 'bullish' if decreases > increases else 'bearish' if increases > decreases else 'stable',
            'changes': changes[:50]  # Keep top 50 changes for analysis
        }

    return trends


def generate_price_change_markdown(changes: Dict[str, List[Tuple[str, float, float, float]]],
                                 trends: Dict[str, Dict],
                                 output_dir: Path, timestamp: datetime) -> Path:
    """Generate a markdown report of price changes with trend analysis."""
    filename = f"price_changes_{timestamp.strftime('%Y%m%d_%H%M%S')}.md"
    path = output_dir / filename

    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# Ardes.bg Price Changes Report\n\n")
        fh.write(f"**Report Date:** {timestamp.strftime('%Y-%m-%d %H:%M UTC')}\n\n")
        fh.write(f"**Analysis Period:** Last 30 days\n\n")

        # Placeholder for AI summary - will be filled later
        fh.write("## Executive Summary\n\n")
        fh.write("*[AI analysis will be inserted here]*\n\n")

        # Trend Analysis Data for AI
        fh.write("## 📊 Market Trend Analysis Data\n\n")
        fh.write("### Multi-Period Trend Statistics\n\n")
        fh.write("| Period | Total Products | Significant Changes | Decreases | Increases | Avg Change | Volatility | Market Direction |\n")
        fh.write("|--------|---------------|-------------------|-----------|-----------|------------|------------|------------------|\n")

        for period in ['14d', '30d', '90d', '180d']:
            if period in trends:
                t = trends[period]
                fh.write(f"| {period} | {t['total_products']} | {t['significant_changes']} | {t['decreases']} | {t['increases']} | {t['avg_change_pct']:.1f}% | {t['volatility']:.1f}% | {t['market_direction']} |\n")

        fh.write("\n### Trend Data for AI Analysis\n\n")
        fh.write("```json\n")
        import json
        fh.write(json.dumps(trends, indent=2, default=str))
        fh.write("\n```\n\n")

        fh.write("## 📈 Notable Price Changes\n\n")

        # Price decreases
        if changes['decreases']:
            fh.write("### 💰 Best Price Improvements\n\n")
            fh.write("| Product | Old Price | New Price | Change |\n")
            fh.write("|---------|-----------|-----------|--------|\n")

            for name, old_price, new_price, change_pct in changes['decreases'][:10]:  # Top 10
                fh.write(f"| {name} | {old_price:.2f} | {new_price:.2f} | {change_pct:.1f}% |\n")

            fh.write("\n")

        # Price increases
        if changes['increases']:
            fh.write("### ⚠️ Price Increases to Watch\n\n")
            fh.write("| Product | Old Price | New Price | Change |\n")
            fh.write("|---------|-----------|-----------|--------|\n")

            for name, old_price, new_price, change_pct in changes['increases'][:10]:  # Top 10
                fh.write(f"| {name} | {old_price:.2f} | {new_price:.2f} | +{change_pct:.1f}% |\n")

            fh.write("\n")

        # New products
        if changes['new_products']:
            fh.write("### 🆕 New Products Added\n\n")
            fh.write("| Product | Price (BGN) |\n")
            fh.write("|---------|-------------|\n")

            for name, _, price, _ in changes['new_products'][:10]:  # Top 10
                fh.write(f"| {name} | {price:.2f} |\n")

            fh.write("\n")

        # Summary statistics
        total_decreases = len(changes['decreases'])
        total_increases = len(changes['increases'])
        total_new = len(changes['new_products'])

        fh.write("## 📊 Summary Statistics\n\n")
        fh.write(f"- **Products with price decreases:** {total_decreases}\n")
        fh.write(f"- **Products with price increases:** {total_increases}\n")
        fh.write(f"- **New products added:** {total_new}\n\n")

        if changes['decreases']:
            avg_decrease = sum(change[3] for change in changes['decreases']) / len(changes['decreases'])
            fh.write(f"- **Average price decrease:** {avg_decrease:.1f}%\n")

        if changes['increases']:
            avg_increase = sum(change[3] for change in changes['increases']) / len(changes['increases'])
            fh.write(f"- **Average price increase:** {avg_increase:.1f}%\n")

        fh.write("\n---\n*Report generated by Ardes Price Scraper*")

    return path


def get_grok_analysis(trend_data: str) -> str:
    """Get AI market analysis from Grok-4 via OpenRouter API."""
    try:
        import openai

        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            # For testing purposes, provide a mock analysis
            return get_mock_analysis(trend_data)

        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )

        prompt = f"""You are a professional PC hardware analyst and PC assembler consultant specializing in the Bulgarian and Eastern European PC components market. Your expertise includes component pricing, market trends, technology developments, and practical PC building advice.

Based on the Ardes.bg price trend data provided, develop a comprehensive market analysis focusing on:

**Market Trend Analysis:**
- Analyze price movements across 14-day, 30-day, 90-day, and 180-day periods
- Identify patterns in market direction (bullish/bearish/stable) across different timeframes
- Assess market volatility and its implications for PC builders and consumers

**Technology & Industry Context:**
- Consider current technology developments (new CPU/GPU releases, DDR5 adoption, etc.)
- Evaluate European market pricing dynamics and regional competition
- Analyze supply chain factors affecting component availability and pricing

**Local Market Hypotheses & Conclusions:**
- Develop hypotheses about Bulgarian PC market dynamics based on observed trends
- Draw conclusions about consumer behavior, retailer strategies, and market positioning
- Consider seasonal factors, economic conditions, and competitive landscape

**PC Building & Purchasing Recommendations:**
- Provide actionable advice for PC builders and system integrators
- Suggest optimal timing for component purchases based on trend analysis
- Recommend strategies for cost optimization and risk management

**Future Market Outlook:**
- Project short-term (1-3 months) and medium-term (3-6 months) market directions
- Identify emerging trends and potential market shifts
- Assess risks and opportunities for PC hardware investments

Focus on developing insights and conclusions rather than merely summarizing the data. Use your expertise to provide valuable analysis that helps PC builders, system integrators, and consumers make informed decisions.

Provide your analysis as a cohesive, professional market report suitable for publication. Include specific recommendations and avoid generic statements.

Trend Data:
{trend_data}

Write a comprehensive market analysis report (600-800 words) that demonstrates deep understanding of the PC hardware market and provides actionable insights."""

        response = client.chat.completions.create(
            model="x-ai/grok-4",  # Using Grok-4 for market analysis
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.7
        )

        return response.choices[0].message.content.strip() if response.choices[0].message.content else "*AI analysis unavailable*"

    except Exception as e:
        LOGGER.warning(f"Failed to get AI analysis: {e}")
        # Fallback to mock analysis
        return get_mock_analysis(trend_data)


def get_mock_analysis(trend_data: str) -> str:
    """Generate a mock AI analysis for testing when API is not available."""
    try:
        trends = json.loads(trend_data)
        analysis = f"""## Mock AI Market Analysis - For Testing Purposes

**Note:** This is a simulated analysis generated for testing. To get real AI analysis, set the OPENROUTER_API_KEY or OPENAI_API_KEY environment variable.

### Market Overview

Based on the Ardes.bg price trend data, the PC hardware market shows the following characteristics:

- **Total Products Monitored:** {trends.get('14d', {}).get('total_products', 'N/A')}
- **Market Direction:** {trends.get('14d', {}).get('market_direction', 'N/A').title()}
- **Average Price Change:** {trends.get('14d', {}).get('avg_change_pct', 0):.1f}%
- **Market Volatility:** {trends.get('14d', {}).get('volatility', 0):.1f}%

## Key Findings

1. **Price Stability:** The market shows moderate stability with significant changes in {trends.get('14d', {}).get('significant_changes', 0)} products.

2. **Trend Direction:** Current bearish market conditions suggest potential buying opportunities for PC builders.

3. **Volatility Assessment:** The {trends.get('14d', {}).get('volatility', 0):.1f}% volatility indicates moderate market uncertainty.

## Recommendations

- **For PC Builders:** Consider timing purchases during bearish periods to optimize costs.
- **For Retailers:** Monitor volatility trends to adjust pricing strategies.
- **For Consumers:** Current market conditions favor planned purchases over impulse buying.

## Future Outlook

The market data suggests continued monitoring is essential for optimal decision-making in the Bulgarian PC hardware sector.

*This mock analysis is for testing only. Configure API keys for real AI-powered insights.*"""
        return analysis
    except Exception as e:
        return f"*Mock analysis generation failed: {e}*"


def update_markdown_with_ai_analysis(md_path: Path, analysis: str) -> None:
    """Update the markdown file with AI analysis in the executive summary section."""
    with md_path.open("r", encoding="utf-8") as fh:
        content = fh.read()

    # Replace the placeholder
    updated_content = content.replace(
        "*[AI analysis will be inserted here]*",
        analysis
    )

    with md_path.open("w", encoding="utf-8") as fh:
        fh.write(updated_content)


def run_scraper(config: ScraperConfig) -> Tuple[Path, Path]:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    LOGGER.info("Starting Ardes price scrape")
    timestamp = datetime.now(timezone.utc)
    records, descriptors = harvest_products(config)
    LOGGER.info("Collected %s products across %s subcategories", len(records), len(descriptors))

    db = PriceDatabase(config.database_path)
    canonical_ids: list[int] = []
    try:
        for record in records:
            product_ref = db.upsert_product(record)
            canonical_ids.append(product_ref)
            db.record_price_if_changed(
                product_ref,
                price_bgn=record.price_bgn,
                deal_price_bgn=record.deal_price_bgn,
                price_eur=record.price_eur,
                timestamp=timestamp,
                min_days_between=config.min_days_between_price_rows,
            )
    finally:
        db.close()

    csv_path = write_csv(records, config.output_dir, timestamp)
    update_csv_with_ids(csv_path, canonical_ids)
    LOGGER.info("CSV written to %s", csv_path)

    # Generate price change analysis
    db = PriceDatabase(config.database_path)
    try:
        changes = analyze_price_changes(db)
        trends = analyze_price_trends(db)
        md_path = generate_price_change_markdown(changes, trends, config.output_dir, timestamp)
        LOGGER.info("Price change markdown written to %s", md_path)

        # Prepare trend data for AI analysis
        import json
        trend_data_for_ai = json.dumps(trends, indent=2, default=str)

        # Get AI market analysis
        ai_analysis = get_grok_analysis(trend_data_for_ai)
        update_markdown_with_ai_analysis(md_path, ai_analysis)
        LOGGER.info("AI analysis added to markdown report")

    finally:
        db.close()

    return csv_path, md_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Download Ardes configurator price lists and persist them")
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml (defaults to ./config.toml)")
    args = parser.parse_args()

    config = ScraperConfig.load(args.config)
    csv_path, md_path = run_scraper(config)
    print(f"CSV report: {csv_path}")
    print(f"Price change analysis: {md_path}")


if __name__ == "__main__":
    main()
