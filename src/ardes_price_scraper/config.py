from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


DEFAULT_CONFIG_PATH = Path("config.toml")


@dataclass(frozen=True)
class ScraperConfig:
    """Application configuration resolved from ``config.toml`` (if present)."""

    base_url: str = "https://ardes.bg/configurator"
    subcat_scan_min: int = 1
    subcat_scan_max: int = 100
    output_dir: Path = Path("output")
    database_path: Path = Path("data") / "ardes_prices.db"
    min_days_between_price_rows: int = 7
    request_timeout_seconds: float = 30.0
    request_retry_attempts: int = 3
    request_backoff_factor: float = 0.5
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    proxy: Optional[str] = None
    allowed_subcats: list[int] = field(default_factory=list)
    category_names: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "ScraperConfig":
        candidates = []
        if path:
            candidates.append(path)
        else:
            # Check multiple possible locations for config.toml
            candidates.extend([
                Path("config.toml"),  # Current directory
                Path("../config.toml"),  # Parent directory (when running from src/)
                Path("../../config.toml"),  # Grandparent (edge case)
            ])
        
        data = {}
        for candidate in candidates:
            if candidate.is_file():
                with candidate.open("rb") as fh:
                    data = tomllib.load(fh)
                break

        general = data.get("general", {})
        scraper = data.get("scraper", {})
        network = data.get("network", {})

        general = data.get("general", {})
        scraper = data.get("scraper", {})
        network = data.get("network", {})

        output_dir = Path(scraper.get("output_dir", cls.output_dir))
        database_path = Path(scraper.get("database_path", cls.database_path))
        allowed_subcats = scraper.get("allowed_subcats", [])
        category_names = scraper.get("category_names", {})

        return cls(
            base_url=scraper.get("base_url", cls.base_url),
            subcat_scan_min=int(scraper.get("subcat_scan_min", cls.subcat_scan_min)),
            subcat_scan_max=int(scraper.get("subcat_scan_max", cls.subcat_scan_max)),
            output_dir=output_dir,
            database_path=database_path,
            min_days_between_price_rows=int(scraper.get("min_days_between_price_rows", cls.min_days_between_price_rows)),
            request_timeout_seconds=float(network.get("timeout_seconds", cls.request_timeout_seconds)),
            request_retry_attempts=int(network.get("retry_attempts", cls.request_retry_attempts)),
            request_backoff_factor=float(network.get("backoff_factor", cls.request_backoff_factor)),
            user_agent=general.get("user_agent", cls.user_agent),
            allowed_subcats=allowed_subcats,
            category_names=category_names,
        )


__all__ = ["ScraperConfig", "DEFAULT_CONFIG_PATH"]
