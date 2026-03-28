from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .normalization import ProductRecord


class PriceDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                normalized_name TEXT NOT NULL,
                latest_raw_name TEXT NOT NULL,
                latest_product_id TEXT,
                subcategory_id INTEGER,
                descriptor TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_ref INTEGER NOT NULL,
                recorded_at TIMESTAMP NOT NULL,
                price_bgn REAL,
                deal_price_bgn REAL,
                price_eur REAL,
                FOREIGN KEY(product_ref) REFERENCES products(id)
            );

            CREATE INDEX IF NOT EXISTS idx_price_history_product_ref
                ON price_history(product_ref, recorded_at DESC);
            """
        )
        self._conn.commit()

    def upsert_product(self, record: ProductRecord) -> int:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO products (slug, normalized_name, latest_raw_name, latest_product_id, subcategory_id, descriptor)
            VALUES (:slug, :normalized_name, :latest_raw_name, :latest_product_id, :subcategory_id, :descriptor)
            ON CONFLICT(slug) DO UPDATE SET
                normalized_name=excluded.normalized_name,
                latest_raw_name=excluded.latest_raw_name,
                latest_product_id=excluded.latest_product_id,
                subcategory_id=excluded.subcategory_id,
                descriptor=excluded.descriptor
            """,
            {
                "slug": record.slug,
                "normalized_name": record.normalized_name,
                "latest_raw_name": record.title,
                "latest_product_id": record.product_id,
                "subcategory_id": record.subcategory_id,
                "descriptor": record.descriptor,
            },
        )
        self._conn.commit()
        return int(cursor.execute("SELECT id FROM products WHERE slug = ?", (record.slug,)).fetchone()[0])

    def record_price_if_changed(
        self,
        product_ref: int,
        *,
        price_bgn: float,
        deal_price_bgn: Optional[float],
        price_eur: Optional[float],
        timestamp: Optional[datetime] = None,
        min_days_between: int = 7,
    ) -> bool:
        timestamp = timestamp or datetime.now(timezone.utc)
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT recorded_at, price_bgn, deal_price_bgn, price_eur
            FROM price_history
            WHERE product_ref = ?
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (product_ref,),
        )
        row = cursor.fetchone()
        if row is not None:
            last_recorded = datetime.fromisoformat(row["recorded_at"])
            if (
                abs(row["price_bgn"] - price_bgn) < 1e-6
                and ((row["deal_price_bgn"] is None and deal_price_bgn is None) or (row["deal_price_bgn"] == deal_price_bgn))
                and ((row["price_eur"] is None and price_eur is None) or (row["price_eur"] == price_eur))
            ):
                if timestamp - last_recorded < timedelta(days=min_days_between):
                    return False

        cursor.execute(
            """
            INSERT INTO price_history (product_ref, recorded_at, price_bgn, deal_price_bgn, price_eur)
            VALUES (:product_ref, :recorded_at, :price_bgn, :deal_price_bgn, :price_eur)
            """,
            {
                "product_ref": product_ref,
                "recorded_at": timestamp.isoformat(),
                "price_bgn": price_bgn,
                "deal_price_bgn": deal_price_bgn,
                "price_eur": price_eur,
            },
        )
        self._conn.commit()
        return True


__all__ = ["PriceDatabase"]
