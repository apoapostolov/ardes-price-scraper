#!/bin/bash
echo "Starting Ardes Price Scraper..."

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "Warning: Virtual environment not found at .venv/bin/activate"
    echo "Make sure Python dependencies are installed."
fi

# Change to src directory
cd src

# Run the scraper
python -m ardes_price_scraper.scraper