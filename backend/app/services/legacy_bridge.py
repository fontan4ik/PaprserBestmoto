from typing import Any, Dict, List, Optional

from ..core.logging import get_logger

logger = get_logger("legacy_bridge")

try:
    from parse_1c_improved import Improved1CParser
except ImportError:
    Improved1CParser = None

try:
    from commerceml_parser import CommerceMLParser
except ImportError:
    CommerceMLParser = None

try:
    from product_matcher import ProductMatcher
except ImportError:
    ProductMatcher = None

try:
    from scrapers.scraper_manager import ScraperManager
except ImportError:
    ScraperManager = None


class LegacyBridge:
    """Wraps legacy scripts so they can be triggered from Celery tasks."""

    def __init__(self):
        self.scraper_manager = ScraperManager(headless=True) if ScraperManager else None

    def parse_1c(self, file_path: str) -> List[Dict[str, Any]]:
        if not Improved1CParser:
            raise RuntimeError("parse_1c_improved module недоступен.")
        parser = Improved1CParser()
        return parser.parse(file_path)

    def parse_commerceml(self, file_path: str) -> List[Dict[str, Any]]:
        if not CommerceMLParser:
            raise RuntimeError("commerceml_parser module недоступен.")
        parser = CommerceMLParser()
        products = parser.parse_file(file_path)
        return [
            product.__dict__ if hasattr(product, "__dict__") else product
            for product in products
        ]

    def match_products(
        self, products_1c: List[Dict[str, Any]], scraped: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not ProductMatcher:
            raise RuntimeError("product_matcher module недоступен.")
        matcher = ProductMatcher()
        results = matcher.match_products(products_1c, scraped)
        return [match.to_dict() if hasattr(match, "to_dict") else match for match in results]

    def scrape_marketplace(
        self, query: str, marketplaces: Optional[List[str]] = None, max_products: int = 50
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not self.scraper_manager:
            raise RuntimeError("scraper_manager module недоступен.")
        results = self.scraper_manager.search_all(
            query=query, sites=marketplaces, max_products=max_products
        )
        return {site: [item.to_dict() for item in items] for site, items in results.items()}

