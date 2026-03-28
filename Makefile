PYTHON ?= python3
OUTPUT ?= output

.PHONY: refresh delta search test

refresh:
	PYTHONPATH=src $(PYTHON) -m ardes_price_scraper.scraper
	PYTHONPATH=src $(PYTHON) -m ardes_price_scraper.report --output-dir $(OUTPUT) --write-latest --top 25

delta:
	PYTHONPATH=src $(PYTHON) -m ardes_price_scraper.report --output-dir $(OUTPUT) --write-latest --top 50

search:
	PYTHONPATH=src $(PYTHON) -m ardes_price_scraper.search_cli "rx 7600" --output-dir $(OUTPUT)

test:
	PYTHONPATH=src $(PYTHON) -m pytest
