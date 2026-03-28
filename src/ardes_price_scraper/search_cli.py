from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .normalization import normalize_name
from .report import latest_csvs, _load_csv, PricePoint


@dataclass
class SearchResult:
    product_id: str
    name: str
    category: str
    price_bgn: float
    deal_price_bgn: Optional[float]
    csv_file: str


def _search_rows(rows: List[PricePoint], query: str, category: Optional[str], limit: int) -> List[PricePoint]:
    q = normalize_name(query)
    results = []
    for row in rows:
        if category and category.lower() not in row.descriptor.lower():
            continue
        name = normalize_name(row.raw_name)
        if all(part in name for part in q.split()):
            results.append(row)
    return results[:limit]


def search_latest(output_dir: Path, query: str, category: Optional[str], limit: int) -> List[SearchResult]:
    csvs = latest_csvs(output_dir, count=1)
    if not csvs:
        raise FileNotFoundError("No CSV files found in output directory.")
    latest = csvs[-1]
    rows_dict = _load_csv(latest)
    rows = list(rows_dict.values())
    matches = _search_rows(rows, query, category, limit)
    return [
        SearchResult(
            product_id=p.product_id,
            name=p.raw_name,
            category=p.descriptor,
            price_bgn=p.price_bgn,
            deal_price_bgn=p.deal_price_bgn,
            csv_file=latest.name,
        )
        for p in matches
    ]


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Quick search over latest Ardes price CSV.")
    parser.add_argument("query", help="Search terms, e.g. 'rx 7600' or 'ryzen 7 7700'")
    parser.add_argument("--output-dir", type=Path, default=Path("output"), help="Directory containing ardes_prices_*.csv files.")
    parser.add_argument("--category", help="Filter by descriptor/category substring (e.g. 'Graphics Cards').")
    parser.add_argument("--limit", type=int, default=15, help="Maximum results to return.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table.")

    args = parser.parse_args(list(argv) if argv is not None else None)

    results = search_latest(args.output_dir, args.query, args.category, args.limit)

    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False))
    else:
        latest_file = results[0].csv_file if results else "n/a"
        print(f"Latest CSV: {latest_file}")
        if not results:
            print("No matches found.")
        for r in results:
            promo = f"{r.deal_price_bgn:.2f}" if r.deal_price_bgn is not None else "—"
            print(f"- {r.name} [{r.category}] list {r.price_bgn:.2f} / promo {promo}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
