@echo off
echo Starting Ardes Price Scraper...

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found at .venv\Scripts\activate.bat
    echo Make sure Python dependencies are installed.
)

REM Change to src directory
cd src

REM Run the scraper
python -m ardes_price_scraper.scraper
)

REM Change to src directory and run the scraper
cd src
echo Running scraper...
python -m ardes_price_scraper.scraper

REM Keep window open to see results
echo.
echo Scraper execution completed.
