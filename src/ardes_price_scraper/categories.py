from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup
from bs4.element import Tag

from .client import build_session, fetch_configurator_markup, iter_subcategory_products
from .config import ScraperConfig

LOGGER = logging.getLogger(__name__)


KEYWORD_MAP: dict[str, str] = {
    "processor": "Processors",
    "intel": "Processors",
    "ryzen": "Processors",
    "core": "Processors",
    "threadripper": "Processors",
    "gpu": "Graphics Cards",
    "geforce": "Graphics Cards",
    "rtx": "Graphics Cards",
    "radeon": "Graphics Cards",
    "gtx": "Graphics Cards",
    "motherboard": "Motherboards",
    "b650": "Motherboards",
    "x670": "Motherboards",
    "z790": "Motherboards",
    "ddr": "Memory (RAM)",
    "so-dimm": "Memory (RAM)",
    "ram": "Memory (RAM)",
    "ssd": "Storage",
    "hdd": "Storage",
    "nvme": "Storage",
    "m.2": "Storage",
    "case": "PC Cases",
    "кутия": "PC Cases",
    "psu": "Power Supplies",
    "захран": "Power Supplies",
    "cooler": "Cooling",
    "охлад": "Cooling",
    "ventilator": "Cooling",
    "fan": "Cooling",
    "windows": "Software",
    "office": "Software",
    "антивирус": "Software",
    "antivirus": "Software",
    "assembly": "Services",
    "дистанцион": "Services",
    "услуга": "Services",
    "monitor": "Peripherals",
    "keyboard": "Peripherals",
    "mouse": "Peripherals",
    "мишк": "Peripherals",
    "клавиат": "Peripherals",
    "router": "Networking",
    "wifi": "Networking",
    "warranty": "Warranty & Insurance",
    "застрахов": "Warranty & Insurance",
    "гаранц": "Warranty & Insurance",
    "printer": "Printers & MFUs",
    "принтер": "Printers & MFUs",
    "mfu": "Printers & MFUs",
    "chair": "Furniture",
    "стол": "Furniture",
    "cable": "Cables & Adapters",
    "кабел": "Cables & Adapters",
}


@dataclass(frozen=True)
class CategoryInsight:
    subcategory_id: int
    descriptor: str
    inferred_category: str
    sample_products: list[str]
    endpoint: str


def discover_categories(config: ScraperConfig, output_path: Path = Path("ARDES_CATEGORIES.md")) -> list[CategoryInsight]:
    session = build_session(config)
    try:
        markup = fetch_configurator_markup(session, config)
        descriptors = extract_descriptors(markup)
        subcats = range(config.subcat_scan_min, config.subcat_scan_max + 1)
        data = iter_subcategory_products(session, config, subcats, limit=10)
    finally:
        session.close()

    insights: list[CategoryInsight] = []
    for subcat, records in sorted(data.items()):
        if not records:
            continue
        titles = [entry.get("title") or entry.get("value") or "" for entry in records]
        descriptor = descriptors.get(subcat, "(unknown)")
        inferred = _infer_category(titles)
        endpoint = f"{config.base_url}?loadSubcatProducts&term=&subcat={subcat}"
        insights.append(
            CategoryInsight(
                subcategory_id=subcat,
                descriptor=descriptor,
                inferred_category=inferred,
                sample_products=titles,
                endpoint=endpoint,
            )
        )

    _write_markdown(output_path, insights)
    LOGGER.info("Documented %s categories to %s", len(insights), output_path)
    return insights


def extract_descriptors(markup: str) -> dict[int, str]:
    soup = BeautifulSoup(markup, "html.parser")
    descriptors: dict[int, str] = {}
    for label in soup.select("label"):
        input_el = label.find(["input", "select"], attrs={"data-subcat": True})
        if not input_el or not isinstance(input_el, Tag):
            continue
        raw_descriptor = label.get_text(" ", strip=True).split("\n", 1)[0].strip()
        subcat_attr = input_el.get("data-subcat")
        if isinstance(subcat_attr, list):
            subcat_str = next((item for item in subcat_attr if isinstance(item, str)), "")
        elif isinstance(subcat_attr, str):
            subcat_str = subcat_attr
        else:
            subcat_str = ""

        if not subcat_str or not subcat_str.isdigit():
            continue
        descriptors[int(subcat_str)] = raw_descriptor
    return descriptors


def _infer_category(titles: Iterable[str]) -> str:
    keyword_counts: Counter[str] = Counter()
    for title in titles:
        lowered = title.lower()
        for keyword, label in KEYWORD_MAP.items():
            if keyword in lowered:
                keyword_counts[label] += 1
    if keyword_counts:
        most_common = keyword_counts.most_common(1)[0][0]
        return most_common
    return "Unclassified"


def _write_markdown(path: Path, insights: Iterable[CategoryInsight]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# Ardes Configurator Subcategories\n\n")
        fh.write("This document lists the publicly accessible JSON price lists discovered under the Ardes PC configurator.\n")
        fh.write("Each section summarises the first ten products returned by the endpoint to help identify the type of items offered.\n\n")
        fh.write("| Subcategory | Descriptor | Inferred Category | JSON Endpoint | Sample Products |\n")
        fh.write("| --- | --- | --- | --- | --- |\n")
        for insight in insights:
            samples = "; ".join(insight.sample_products)
            fh.write(
                f"| {insight.subcategory_id} | {insight.descriptor} | {insight.inferred_category} | "
                f"[{insight.endpoint}]({insight.endpoint}) | {samples} |\n"
            )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Discover Ardes configurator JSON feeds and document them")
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml (defaults to ./config.toml)")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ARDES_CATEGORIES.md"),
        help="Where to write the markdown summary",
    )
    args = parser.parse_args()

    config = ScraperConfig.load(args.config)
    discover_categories(config, output_path=args.output)


if __name__ == "__main__":
    main()


__all__ = ["discover_categories", "CategoryInsight", "extract_descriptors"]
