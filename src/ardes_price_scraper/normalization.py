from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

NORMALIZE_WHITESPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name).strip().lower()
    normalized = NORMALIZE_WHITESPACE_RE.sub(" ", normalized)
    return normalized


def slugify_name(name: str) -> str:
    normalized = normalize_name(name)
    slug = NON_ALNUM_RE.sub("-", normalized).strip("-")
    return slug or "unnamed-product"


@dataclass(frozen=True)
class ProductRecord:
    subcategory_id: int
    descriptor: str
    title: str
    normalized_name: str
    slug: str
    product_id: str
    price_bgn: float
    deal_price_bgn: float | None
    price_eur: float | None


__all__ = ["normalize_name", "slugify_name", "ProductRecord"]
