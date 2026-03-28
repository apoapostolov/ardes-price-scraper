@echo off
echo Starting Ardes Price Scraper...

REM Load environment variables from .env.shared
if exist "..\..\.docs\.env.shared" (
    echo Loading environment variables from .env.shared...
    for /f "tokens=1,2 delims==" %%a in ('findstr "^OPENROUTER_API_KEY=" "..\..\.docs\.env.shared"') do set %%a=%%b
    for /f "tokens=1,2 delims==" %%a in ('findstr "^OPENAI_API_KEY=" "..\..\.docs\.env.shared"') do set %%a=%%b
    for /f "tokens=1,2 delims==" %%a in ('findstr "^TAVILY_API_KEY=" "..\..\.docs\.env.shared"') do set %%a=%%b
) else (
    echo Warning: .env.shared file not found at ..\..\.docs\.env.shared
)

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found at .venv\Scripts\activate.bat
    echo Make sure Python dependencies are installed.
)

REM Change to src directory and run the scraper
cd src
echo Running scraper...
python -m ardes_price_scraper.scraper

REM Keep window open to see results
echo.
echo Scraper execution completed.
