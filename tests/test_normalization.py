from ardes_price_scraper.normalization import normalize_name, slugify_name


def test_normalize_name_strips_and_lowercases():
    assert normalize_name("  AMD   Ryzen 5  ") == "amd ryzen 5"


def test_slugify_generates_hyphenated_lowercase():
    assert slugify_name("GeForce RTX 4090") == "geforce-rtx-4090"


def test_slugify_fallback_for_empty():
    assert slugify_name("   ") == "unnamed-product"
