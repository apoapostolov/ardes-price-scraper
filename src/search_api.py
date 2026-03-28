#!/usr/bin/env python3
"""
Ardes Price Database Search API

This script provides an efficient way for AI systems to query the Ardes price database
without having to parse large CSV files. It supports various search criteria and returns
structured JSON data.

Usage:
    python search_api.py "rtx 4070" --type "Graphics Cards"
    python search_api.py --manufacturer "NVIDIA" --max-price 1000
    python search_api.py "DDR5" --category "Memory (RAM)"
"""

import argparse
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import re


class ArdesPriceSearch:
    """Search API for Ardes price database."""

    def __init__(self, db_path: str = "data/ardes_prices.db"):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _extract_manufacturer(self, product_name: str) -> str:
        """Extract manufacturer from product name using common patterns."""
        # Common manufacturer patterns
        manufacturers = {
            'nvidia': ['rtx', 'gtx', 'geforce', 'titan'],
            'amd': ['ryzen', 'radeon', 'epyc', 'threadripper'],
            'intel': ['core i', 'pentium', 'celeron', 'xeon'],
            'asus': ['rog', 'tuf', 'prime'],
            'msi': ['gaming', 'mag'],
            'gigabyte': ['aorus', 'gaming'],
            'corsair': ['icue', 'h', 'hx', 'rm'],
            'kingston': ['fury', 'hyperx'],
            'crucial': ['ballistix'],
            'samsung': [],
            'western digital': ['wd ', 'black', 'blue'],
            'seagate': ['barracuda', 'firecuda'],
            'noctua': ['nh-'],
            'be quiet': ['dark rock', 'pure'],
            'cooler master': ['hyper', 'masterair'],
        }

        name_lower = product_name.lower()

        # Direct manufacturer matches
        for manufacturer, keywords in manufacturers.items():
            if manufacturer in name_lower:
                return manufacturer.title()
            for keyword in keywords:
                if keyword in name_lower:
                    return manufacturer.title()

        # Extract from beginning of name (common pattern)
        words = product_name.split()
        if words:
            first_word = words[0].lower()
            # Skip common non-manufacturer words
            if first_word not in ['the', 'a', 'an', 'with', 'for', 'by', '8gb', '16gb', '32gb', '64gb', '1tb', '2tb', '4tb', '500gb', '256gb', '512gb']:
                return first_word.title()

        return "Unknown"

    def search_products(self,
                       query: Optional[str] = None,
                       manufacturer: Optional[str] = None,
                       category: Optional[str] = None,
                       subcategory_id: Optional[int] = None,
                       min_price: Optional[float] = None,
                       max_price: Optional[float] = None,
                       limit: int = 50) -> Dict[str, Any]:
        """
        Search products with various criteria.

        Args:
            query: Partial product name to search for
            manufacturer: Filter by manufacturer
            category: Filter by category (descriptor)
            subcategory_id: Filter by subcategory ID
            min_price: Minimum price filter
            max_price: Maximum price filter
            limit: Maximum results to return

        Returns:
            Dict containing search results and metadata
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Build query
        sql = """
        SELECT
            p.id,
            p.slug,
            p.normalized_name,
            p.latest_raw_name,
            p.subcategory_id,
            p.descriptor,
            ph.price_bgn,
            ph.deal_price_bgn,
            ph.price_eur,
            ph.recorded_at
        FROM products p
        JOIN price_history ph ON p.id = ph.product_ref
        WHERE ph.id IN (
            SELECT MAX(ph2.id)
            FROM price_history ph2
            WHERE ph2.product_ref = p.id
        )
        """

        params = []
        conditions = []

        if query:
            conditions.append("(p.normalized_name LIKE ? OR p.latest_raw_name LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        if manufacturer:
            # Search in product names for manufacturer
            conditions.append("(p.normalized_name LIKE ? OR p.latest_raw_name LIKE ?)")
            params.extend([f"%{manufacturer}%", f"%{manufacturer}%"])

        if category:
            conditions.append("p.descriptor LIKE ?")
            params.append(f"%{category}%")

        if subcategory_id:
            conditions.append("p.subcategory_id = ?")
            params.append(subcategory_id)

        if min_price is not None:
            conditions.append("ph.price_bgn >= ?")
            params.append(min_price)

        if max_price is not None:
            conditions.append("ph.price_bgn <= ?")
            params.append(max_price)

        if conditions:
            sql += " AND " + " AND ".join(conditions)

        sql += " ORDER BY ph.recorded_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            product_id, slug, normalized_name, raw_name, subcategory_id, descriptor, price_bgn, deal_price_bgn, price_eur, recorded_at = row

            # Extract manufacturer
            extracted_manufacturer = self._extract_manufacturer(raw_name)

            results.append({
                "id": product_id,
                "slug": slug,
                "name": normalized_name,
                "raw_name": raw_name,
                "manufacturer": extracted_manufacturer,
                "category": descriptor,
                "subcategory_id": subcategory_id,
                "price_bgn": price_bgn,
                "deal_price_bgn": deal_price_bgn,
                "price_eur": price_eur,
                "last_updated": recorded_at,
                "url": f"https://ardes.bg/configurator?product={product_id}"
            })

        # Get search metadata
        cursor.execute("SELECT COUNT(*) FROM products")
        total_products = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT descriptor) FROM products")
        total_categories = cursor.fetchone()[0]

        conn.close()

        return {
            "query": {
                "search_term": query,
                "manufacturer": manufacturer,
                "category": category,
                "subcategory_id": subcategory_id,
                "price_range": {"min": min_price, "max": max_price},
                "limit": limit
            },
            "results": results,
            "metadata": {
                "total_results": len(results),
                "total_products_in_db": total_products,
                "total_categories": total_categories,
                "search_timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all available categories with product counts."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT descriptor, subcategory_id, COUNT(*) as product_count
            FROM products
            GROUP BY descriptor, subcategory_id
            ORDER BY descriptor
        """)

        categories = []
        for row in cursor.fetchall():
            descriptor, subcategory_id, count = row
            categories.append({
                "name": descriptor,
                "subcategory_id": subcategory_id,
                "product_count": count
            })

        conn.close()
        return categories

    def get_manufacturers(self) -> List[Dict[str, Any]]:
        """Get all manufacturers with product counts."""
        results = self.search_products(limit=10000)  # Get all products
        manufacturers = {}

        for product in results["results"]:
            manufacturer = product["manufacturer"]
            if manufacturer not in manufacturers:
                manufacturers[manufacturer] = 0
            manufacturers[manufacturer] += 1

        return [
            {"name": name, "product_count": count}
            for name, count in sorted(manufacturers.items(), key=lambda x: x[1], reverse=True)
        ]

    def get_price_stats(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get price statistics for a category or all products."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if category:
            cursor.execute("""
                SELECT
                    COUNT(*) as count,
                    AVG(ph.price_bgn) as avg_price,
                    MIN(ph.price_bgn) as min_price,
                    MAX(ph.price_bgn) as max_price
                FROM products p
                JOIN price_history ph ON p.id = ph.product_ref
                WHERE p.descriptor LIKE ?
                AND ph.id IN (
                    SELECT MAX(ph2.id)
                    FROM price_history ph2
                    WHERE ph2.product_ref = p.id
                )
            """, (f"%{category}%",))
        else:
            cursor.execute("""
                SELECT
                    COUNT(*) as count,
                    AVG(ph.price_bgn) as avg_price,
                    MIN(ph.price_bgn) as min_price,
                    MAX(ph.price_bgn) as max_price
                FROM products p
                JOIN price_history ph ON p.id = ph.product_ref
                WHERE ph.id IN (
                    SELECT MAX(ph2.id)
                    FROM price_history ph2
                    WHERE ph2.product_ref = p.id
                )
            """)

        row = cursor.fetchone()
        count, avg_price, min_price, max_price = row

        conn.close()

        return {
            "category": category or "all",
            "product_count": count,
            "average_price_bgn": round(avg_price, 2) if avg_price else None,
            "min_price_bgn": min_price,
            "max_price_bgn": max_price
        }


def main():
    parser = argparse.ArgumentParser(description="Search Ardes Price Database")
    parser.add_argument("query", nargs="?", help="Product name to search for")
    parser.add_argument("--manufacturer", "-m", help="Filter by manufacturer")
    parser.add_argument("--category", "-c", help="Filter by category")
    parser.add_argument("--subcategory-id", "-s", type=int, help="Filter by subcategory ID")
    parser.add_argument("--min-price", type=float, help="Minimum price filter")
    parser.add_argument("--max-price", type=float, help="Maximum price filter")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Maximum results")
    parser.add_argument("--format", "-f", choices=["json", "text"], default="json", help="Output format")
    parser.add_argument("--command", choices=["search", "categories", "manufacturers", "stats"],
                       default="search", help="Command to execute")

    args = parser.parse_args()

    try:
        search = ArdesPriceSearch()

        if args.command == "search":
            results = search.search_products(
                query=args.query,
                manufacturer=args.manufacturer,
                category=args.category,
                subcategory_id=args.subcategory_id,
                min_price=args.min_price,
                max_price=args.max_price,
                limit=args.limit
            )

            if args.format == "json":
                print(json.dumps(results, indent=2, ensure_ascii=False))
            else:
                print(f"Found {results['metadata']['total_results']} products:")
                for product in results["results"]:
                    print(f"- {product['name']}: {product['price_bgn']} BGN ({product['manufacturer']})")

        elif args.command == "categories":
            categories = search.get_categories()
            if args.format == "json":
                print(json.dumps(categories, indent=2, ensure_ascii=False))
            else:
                print("Available categories:")
                for cat in categories:
                    print(f"- {cat['name']} ({cat['product_count']} products)")

        elif args.command == "manufacturers":
            manufacturers = search.get_manufacturers()
            if args.format == "json":
                print(json.dumps(manufacturers, indent=2, ensure_ascii=False))
            else:
                print("Manufacturers by product count:")
                for mfg in manufacturers[:20]:  # Top 20
                    print(f"- {mfg['name']}: {mfg['product_count']} products")

        elif args.command == "stats":
            stats = search.get_price_stats(args.category)
            if args.format == "json":
                print(json.dumps(stats, indent=2, ensure_ascii=False))
            else:
                print(f"Price statistics for '{stats['category']}':")
                print(f"- Products: {stats['product_count']}")
                print(f"- Average price: {stats['average_price_bgn']} BGN")
                print(f"- Price range: {stats['min_price_bgn']} - {stats['max_price_bgn']} BGN")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import sys
    main()