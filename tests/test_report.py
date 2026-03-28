from pathlib import Path

from ardes_price_scraper import report


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_csv_requires_columns():
    data = report._load_csv(FIXTURES / "prices_old.csv")
    assert "1001" in data
    cpu = data["1001"]
    assert cpu.raw_name.startswith("AMD Ryzen 7 7700")
    assert cpu.deal_price_bgn == 552.60


def test_compute_changes_detects_delta_and_additions():
    old_path = FIXTURES / "prices_old.csv"
    new_path = FIXTURES / "prices_new.csv"

    diff = report.compute_changes(old_path, new_path, top=10)

    changed = {(n.product_id, round(delta, 1)) for n, _, delta in diff["changed"]}
    assert ("1001", -9.5) in changed  # Ryzen promo drop
    assert ("2001", -8.3) in changed  # RAM promo drop

    added_ids = {n.product_id for n, _, _ in diff["added"]}
    assert "2002" in added_ids

    # No removals in fixture
    assert diff["removed"] == []
