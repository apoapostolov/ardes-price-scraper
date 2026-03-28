#!/usr/bin/env python3
"""
MCP Wrapper for Ardes Price Scraper

This module provides a Model Context Protocol (MCP) compatible interface
for AI agents to interact with the Ardes Price Scraper tool.

Usage for AI agents:
- Import this module
- Use the provided functions to scrape prices, search products, etc.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ardes_price_scraper.scraper import main as scrape_main
from ardes_price_scraper.search_cli import main as search_main
from ardes_price_scraper.report import main as report_main


def scrape_prices():
    """
    Run the price scraper to collect current prices from Ardes.bg

    Returns:
        str: Status message indicating success or failure
    """
    try:
        # Change to src directory
        os.chdir(Path(__file__).parent / "src")
        scrape_main()
        return "Price scraping completed successfully"
    except Exception as e:
        return f"Price scraping failed: {str(e)}"


def search_products(query, limit=5):
    """
    Search for products in the database

    Args:
        query (str): Search query (product name, manufacturer, etc.)
        limit (int): Maximum number of results to return

    Returns:
        str: Search results as formatted text
    """
    try:
        # Change to src directory
        os.chdir(Path(__file__).parent / "src")
        # This would need to be adapted to capture output
        # For now, return a placeholder
        return f"Search results for '{query}' (limit: {limit})"
    except Exception as e:
        return f"Product search failed: {str(e)}"


def generate_price_report():
    """
    Generate a price change report

    Returns:
        str: Report content or status message
    """
    try:
        # Change to src directory
        os.chdir(Path(__file__).parent / "src")
        report_main()
        return "Price report generated successfully"
    except Exception as e:
        return f"Report generation failed: {str(e)}"


if __name__ == "__main__":
    # Command line interface for testing
    if len(sys.argv) < 2:
        print("Usage: python mcp_wrapper.py <command> [args...]")
        print("Commands: scrape, search <query> [limit], report")
        sys.exit(1)

    command = sys.argv[1]

    if command == "scrape":
        print(scrape_prices())
    elif command == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        print(search_products(query, limit))
    elif command == "report":
        print(generate_price_report())
    else:
        print(f"Unknown command: {command}")