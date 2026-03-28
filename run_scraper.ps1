Write-Host "Starting Ardes Price Scraper..."

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..."
    & ".venv\Scripts\Activate.ps1"
} else {
    Write-Host "Warning: Virtual environment not found at .venv\Scripts\Activate.ps1"
    Write-Host "Make sure Python dependencies are installed."
}

# Change to src directory
Set-Location src

# Run the scraper
python -m ardes_price_scraper.scraper