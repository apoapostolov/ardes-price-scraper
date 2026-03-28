from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


REQUIRED_COLUMNS = [
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


@dataclass(frozen=True)
class PricePoint:
    product_id: str
    raw_name: str
    descriptor: str
    normalized_name: str
    price_bgn: float
    deal_price_bgn: Optional[float]

    @property
    def effective_price(self) -> float:
        return self.deal_price_bgn if self.deal_price_bgn is not None else self.price_bgn


def _load_csv(path: Path) -> Dict[str, PricePoint]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise ValueError(f"{path} missing columns: {', '.join(missing)}")

        rows: Dict[str, PricePoint] = {}
        for row in reader:
            deal = row.get("deal_price_bgn")
            deal_price = float(deal) if deal not in (None, "", "null") else None
            rows[row["product_id"]] = PricePoint(
                product_id=row["product_id"],
                raw_name=row["raw_name"],
                descriptor=row["descriptor"],
                normalized_name=row["normalized_name"],
                price_bgn=float(row["price_bgn"]),
                deal_price_bgn=deal_price,
            )
        return rows


def _find_csvs(output_dir: Path) -> List[Path]:
    return sorted(output_dir.glob("ardes_prices_*.csv"))


def latest_csvs(output_dir: Path, count: int = 2) -> List[Path]:
    csvs = _find_csvs(output_dir)
    return csvs[-count:]


def _pct_change(old: float, new: float) -> float:
    if old == 0:
        return 0.0
    return ((new - old) / old) * 100


def compute_changes(old_path: Path, new_path: Path, top: int = 25) -> Dict[str, List[Tuple[PricePoint, Optional[PricePoint], float]]]:
    old = _load_csv(old_path)
    new = _load_csv(new_path)

    changes: List[Tuple[PricePoint, PricePoint, float]] = []
    added: List[Tuple[PricePoint, None, float]] = []
    removed: List[Tuple[PricePoint, None, float]] = []

    for product_id, new_item in new.items():
        if product_id in old:
            old_item = old[product_id]
            delta_pct = _pct_change(old_item.effective_price, new_item.effective_price)
            if abs(delta_pct) > 0.01:
                changes.append((new_item, old_item, delta_pct))
        else:
            added.append((new_item, None, 0.0))

    for product_id, old_item in old.items():
        if product_id not in new:
            removed.append((old_item, None, 0.0))

    changes_sorted = sorted(changes, key=lambda tup: abs(tup[2]), reverse=True)[:top]
    added_sorted = sorted(added, key=lambda tup: tup[0].effective_price)[:top]
    removed_sorted = sorted(removed, key=lambda tup: tup[0].effective_price)[:top]

    return {
        "changed": changes_sorted,
        "added": added_sorted,
        "removed": removed_sorted,
    }


def format_markdown(old_path: Path, new_path: Path, diff: Dict[str, List[Tuple[PricePoint, Optional[PricePoint], float]]]) -> str:
    def price(p: PricePoint) -> str:
        if p.deal_price_bgn is not None:
            return f"{p.deal_price_bgn:.2f} (deal) / {p.price_bgn:.2f} list"
        return f"{p.price_bgn:.2f} list"

    lines: List[str] = []
    lines.append(f"# Ardes Price Delta")
    lines.append("")
    lines.append(f"- New CSV: `{new_path.name}`")
    lines.append(f"- Old CSV: `{old_path.name}`")
    lines.append("")

    if diff["changed"]:
        lines.append("## Top Price Changes")
        lines.append("")
        lines.append("| Product | Old | New | Δ % | Category |")
        lines.append("|---|---|---|---|---|")
        for new_item, old_item, delta_pct in diff["changed"]:
            assert old_item is not None
            lines.append(
                f"| {new_item.raw_name} | {price(old_item)} | {price(new_item)} | {delta_pct:+.1f}% | {new_item.descriptor} |"
            )
        lines.append("")

    if diff["added"]:
        lines.append("## Newly Added (top by lowest price)")
        lines.append("")
        lines.append("| Product | Price | Category |")
        lines.append("|---|---|---|")
        for new_item, _, _ in diff["added"]:
            lines.append(f"| {new_item.raw_name} | {price(new_item)} | {new_item.descriptor} |")
        lines.append("")

    if diff["removed"]:
        lines.append("## Removed (top by lowest price)")
        lines.append("")
        lines.append("| Product | Last Known Price | Category |")
        lines.append("|---|---|---|")
        for old_item, _, _ in diff["removed"]:
            lines.append(f"| {old_item.raw_name} | {price(old_item)} | {old_item.descriptor} |")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_latest_delta(output_dir: Path, top: int = 25) -> Path:
    csvs = latest_csvs(output_dir, count=2)
    if len(csvs) < 2:
        raise FileNotFoundError("Need at least two CSV files to compute a delta report.")
    old_path, new_path = csvs[-2], csvs[-1]
    diff = compute_changes(old_path, new_path, top=top)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"price_changes_{ts}.md"
    out_path.write_text(format_markdown(old_path, new_path, diff), encoding="utf-8")
    return out_path


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate price change markdown between latest Ardes CSV dumps.")
    parser.add_argument("--output-dir", type=Path, default=Path("output"), help="Directory containing ardes_prices_*.csv files.")
    parser.add_argument("--old", type=Path, help="Override old CSV path.")
    parser.add_argument("--new", type=Path, help="Override new CSV path.")
    parser.add_argument("--top", type=int, default=25, help="Number of rows for each section.")
    parser.add_argument("--write-latest", action="store_true", help="Write markdown to output/price_changes_<timestamp>.md")

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.old and args.new:
        old_path, new_path = args.old, args.new
    else:
        csvs = latest_csvs(args.output_dir, count=2)
        if len(csvs) < 2:
            raise FileNotFoundError("Need at least two CSV files to compute a delta report.")
        old_path, new_path = csvs[-2], csvs[-1]

    diff = compute_changes(old_path, new_path, top=args.top)
    markdown = format_markdown(old_path, new_path, diff)

    if args.write_latest:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = args.output_dir / f"price_changes_{ts}.md"
        out_path.write_text(markdown, encoding="utf-8")
        print(f"Wrote {out_path}")
    else:
        print(markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
