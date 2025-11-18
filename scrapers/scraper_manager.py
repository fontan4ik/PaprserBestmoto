"""
Менеджер скраперов
Управляет всеми Selenium скраперами и предоставляет единый интерфейс
"""

from typing import List, Dict, Optional
import logging
import re
from dataclasses import dataclass, asdict

from .wildberries_scraper import WildberriesScraper
from .ozon_scraper import OzonScraper
from .avito_scraper import AvitoScraper
from .yandex_market_scraper import YandexMarketScraper
from .universal_scraper import UniversalScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScrapedProduct:
    """Унифицированная структура товара"""
    title: str
    price: float
    old_price: Optional[float] = None
    url: str = ""
    source: str = ""
    availability: str = "unknown"
    brand: str = ""
    rating: float = 0.0
    reviews_count: int = 0
    image_url: str = ""
    location: str = ""
    seller: str = ""
    
    def to_dict(self):
        """Конвертирует в словарь"""
        return asdict(self)


class ScraperManager:
    """
    Менеджер всех скраперов
    Предоставляет единый интерфейс для парсинга всех маркетплейсов
    """
    
    SUPPORTED_SITES = {
        'wildberries': 'Wildberries',
        'ozon': 'OZON',
        'avito': 'Avito',
        'yandex_market': 'Яндекс Маркет',
        'mr-moto': 'mr-moto.ru',
        'flipup': 'flipup.ru',
        'pro-ekip': 'pro-ekip.ru',
        'motoekip': 'motoekip.su',
        'motocomfort': 'motocomfort.ru',
    }
    
    SITE_ALIASES = {
        'mrmotoru': 'mr-moto',
        'flipupru': 'flipup',
        'proekipru': 'pro-ekip',
        'motoekipsu': 'motoekip',
        'motocomfortru': 'motocomfort',
    }
    
    def __init__(self, headless: bool = True):
        """
        Args:
            headless: запускать браузер в headless режиме
        """
        self.headless = headless
        self._scrapers = {}
        self.logger = logging.getLogger(__name__)
    
    def search_all(self, query: str, sites: Optional[List[str]] = None, max_products: int = 20) -> Dict[str, List[ScrapedProduct]]:
        """
        Поиск на всех или указанных сайтах
        
        Args:
            query: поисковый запрос
            sites: список сайтов (если None - поиск на всех)
            max_products: максимум товаров с каждого сайта
        
        Returns:
            словарь {сайт: [товары]}
        """
        if sites is None:
            sites = list(self.SUPPORTED_SITES.keys())
        
        results = {}
        
        for site in sites:
            canonical_site = self._normalize_site_key(site)
            if not canonical_site:
                self.logger.warning(f"⚠️ Неизвестный сайт: {site}")
                continue
            
            try:
                products = self.search(canonical_site, query, max_products)
                results[canonical_site] = products
                self.logger.info(f"✅ {canonical_site}: найдено {len(products)} товаров")
            except Exception as e:
                self.logger.error(f"❌ Ошибка на {canonical_site}: {e}")
                results[canonical_site] = []
        
        return results
    
    def search(self, site: str, query: str, max_products: int = 20) -> List[ScrapedProduct]:
        """
        Поиск на конкретном сайте
        
        Args:
            site: название сайта
            query: поисковый запрос
            max_products: максимум товаров
        
        Returns:
            список товаров
        """
        canonical_site = self._normalize_site_key(site)
        if not canonical_site:
            self.logger.warning(f"⚠️ Неизвестный сайт: {site}")
            return []
        
        self.logger.info(f"🔍 Поиск на {canonical_site}: '{query}'")
        
        products = []
        
        try:
            if canonical_site == 'wildberries':
                products = self._search_wildberries(query, max_products)
            
            elif canonical_site == 'ozon':
                products = self._search_ozon(query, max_products)
            
            elif canonical_site == 'avito':
                products = self._search_avito(query, max_products)
            
            elif canonical_site == 'yandex_market':
                products = self._search_yandex_market(query, max_products)
            
            elif canonical_site in ['mr-moto', 'flipup', 'pro-ekip', 'motoekip', 'motocomfort']:
                domain = self.SUPPORTED_SITES[canonical_site]
                products = self._search_universal(domain, query, max_products)
            
            else:
                self.logger.warning(f"⚠️ Неизвестный сайт: {canonical_site}")
            
            # Конвертируем в унифицированный формат
            unified_products = []
            for p in products:
                unified = ScrapedProduct(
                    title=p.title,
                    price=p.price,
                    old_price=getattr(p, 'old_price', None),
                    url=p.url,
                    source=p.source,
                    availability=getattr(p, 'availability', 'unknown'),
                    brand=getattr(p, 'brand', ''),
                    rating=getattr(p, 'rating', 0.0),
                    reviews_count=getattr(p, 'reviews_count', 0),
                    image_url=getattr(p, 'image_url', ''),
                    location=getattr(p, 'location', ''),
                    seller=getattr(p, 'seller', ''),
                )
                unified_products.append(unified)
            
            return unified_products
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка поиска на {canonical_site}: {e}")
            return []
    
    def _get_scraper(self, scraper_name: str, scraper_class):
        """Получить или создать скрапер (с кешированием)"""
        if scraper_name not in self._scrapers:
            self._scrapers[scraper_name] = scraper_class(headless=self.headless)
        return self._scrapers[scraper_name]
    
    def _search_wildberries(self, query: str, max_products: int) -> List:
        """Поиск на Wildberries"""
        scraper = self._get_scraper('wildberries', WildberriesScraper)
        return scraper.search(query, max_products)
    
    def _search_ozon(self, query: str, max_products: int) -> List:
        """Поиск на OZON"""
        scraper = self._get_scraper('ozon', OzonScraper)
        return scraper.search(query, max_products)
    
    def _search_avito(self, query: str, max_products: int) -> List:
        """Поиск на Avito"""
        scraper = self._get_scraper('avito', AvitoScraper)
        return scraper.search(query, max_products)
    
    def _search_yandex_market(self, query: str, max_products: int) -> List:
        """Поиск на Яндекс Маркет"""
        scraper = self._get_scraper('yandex_market', YandexMarketScraper)
        return scraper.search(query, max_products)
    
    def _search_universal(self, site: str, query: str, max_products: int) -> List:
        """Поиск на универсальных сайтах"""
        scraper_key = f'universal_{site}'
        if scraper_key not in self._scrapers:
            self._scrapers[scraper_key] = UniversalScraper(headless=self.headless)
        scraper = self._scrapers[scraper_key]
        return scraper.search(site, query, max_products)
    
    def close_all(self):
        """Закрыть все браузеры"""
        for name, scraper in self._scrapers.items():
            try:
                scraper.close()
                self.logger.info(f"🔒 Закрыт скрапер: {name}")
            except Exception as e:
                self.logger.warning(f"⚠️ Ошибка закрытия {name}: {e}")
        self._scrapers.clear()
    
    def __del__(self):
        """Деструктор - закрываем все браузеры"""
        try:
            self.close_all()
        except:
            pass
    
    def get_supported_sites(self) -> Dict[str, str]:
        """Возвращает список поддерживаемых сайтов"""
        return self.SUPPORTED_SITES.copy()
    
    def _normalize_site_key(self, site: Optional[str]) -> Optional[str]:
        """Приводит входящее имя сайта к каноническому ключу"""
        if not site:
            return None
        
        if site in self.SUPPORTED_SITES:
            return site
        
        sanitized = re.sub(r'[\s\-.]', '', site.lower())
        alias = self.SITE_ALIASES.get(sanitized)
        if alias:
            return alias
        
        # Дополнительно пробуем убрать www
        if sanitized.startswith('www'):
            alias = self.SITE_ALIASES.get(sanitized[3:])
            if alias:
                return alias
        
        return None


# Тестирование
if __name__ == "__main__":
    print("=" * 80)
    print("  ТЕСТ SCRAPER MANAGER")
    print("=" * 80)
    print()
    
    manager = ScraperManager(headless=True)
    
    # Показываем поддерживаемые сайты
    print("Поддерживаемые сайты:")
    for key, name in manager.get_supported_sites().items():
        print(f"  - {key}: {name}")
    
    print("\n" + "=" * 80)
    print("  Тестовый поиск")
    print("=" * 80)
    
    # Тестируем поиск на нескольких сайтах
    query = "мотошлем HJC"
    sites = ['wildberries', 'ozon']  # Тестируем только 2 сайта
    
    print(f"\n🔍 Запрос: '{query}'")
    print(f"📍 Сайты: {', '.join(sites)}")
    print()
    
    results = manager.search_all(query, sites=sites, max_products=3)
    
    # Выводим результаты
    for site, products in results.items():
        print(f"\n{'='*80}")
        print(f"  {site.upper()}: {len(products)} товаров")
        print(f"{'='*80}")
        
        if products:
            for i, product in enumerate(products, 1):
                print(f"\n{i}. {product.title[:60]}...")
                print(f"   💰 Цена: {product.price:,.0f}₽")
                if product.old_price:
                    print(f"   💸 Было: {product.old_price:,.0f}₽")
                if product.rating > 0:
                    print(f"   ⭐ Рейтинг: {product.rating}")
                print(f"   🔗 {product.url}")
        else:
            print("\n⚠️ Товары не найдены")
    
    print("\n" + "=" * 80)
    print("  ✅ Тестирование завершено")
    print("=" * 80)
