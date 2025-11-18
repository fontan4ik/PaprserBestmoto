"""
Универсальный Selenium скрапер для небольших интернет-магазинов
Работает с: mr-moto.ru, Flipup.ru, Pro-ekip.ru, Motoekip.su, Motocomfort.ru
На основе отчета по инспекции mr-moto.ru
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import re
import logging
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import quote_plus
import random

@dataclass
class Product:
    title: str
    price: float
    old_price: Optional[float] = None
    url: str = ""
    source: str = ""
    availability: str = "unknown"
    brand: str = ""
    image_url: str = ""


class UniversalScraper:
    """
    Универсальный скрапер для небольших интернет-магазинов
    Автоматически определяет структуру сайта и извлекает данные
    """
    
    # Конфигурация сайтов
    SITES_CONFIG = {
        'mr-moto.ru': {
            'search_url': 'https://mr-moto.ru/catalog/search/?q={query}',
            'product_card_selectors': ['div.slider-card', 'div.slider-card__box'],
            'title_selectors': [
                'div.slider-card__title a[href]',
                'div.slider-card__box a[href]'
            ],
            'brand_selectors': ['div.slider-card__box > div.slider-card__title a[target="_blank"]'],
            'price_selectors': [
                'div.slider-card__price-title',
                {'selector': 'meta[itemprop="lowPrice"]', 'attr': 'content'},
            ],
        },
        'flipup.ru': {
            'search_url': 'https://flipup.ru/search/?q={query}',
            'product_card_selectors': ['div.product-card', 'div.product-item'],
            'title_selectors': [
                'a.name span.middle',
                'a.name'
            ],
            'price_selectors': [
                'a.price',
                'div.price',
                'span.price'
            ],
        },
        'pro-ekip.ru': {
            'search_url': 'https://pro-ekip.ru/catalog/?q={query}',
            'product_card_selectors': ['div.item', 'div.product', 'div.catalog-item'],
            'title_selectors': [
                'a.thumb.shine',
                'a.thumb',
                'a.title'
            ],
            'price_selectors': [
                {'selector': 'span.to-cart', 'attr': 'data-value'},
                'div.cost',
                'span.price'
            ],
        },
        'motoekip.su': {
            'search_url': 'https://motoekip.su/index.php?route=product/search&search={query}',
            'product_card_selectors': ['div.digi-product', 'div.digi-product__layout'],
            'title_selectors': [
                'a.digi-product__label',
                'a.digi-product__brand'
            ],
            'brand_selectors': ['a.digi-product__brand'],
            'price_selectors': [
                'span.digi-product-price-variant_actual',
                'div.digi-product__price'
            ],
        },
        'motocomfort.ru': {
            'search_url': 'https://motocomfort.ru/search/?query={query}',
            'product_card_selectors': ['div.c-product-thumb', 'div.c-product-thumb__wrapper'],
            'title_selectors': [
                'div.c-product-thumb__name a',
                {'selector': 'img.c-product-thumb__image', 'attr': 'data-alt'},
                {'selector': 'img.c-product-thumb__image', 'attr': 'alt'},
            ],
            'price_selectors': [
                'div.c-product-thumb__price',
                'span.c-product-thumb__price',
                'span.price'
            ],
        },
    }
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
    
    def _init_driver(self):
        """Инициализация драйвера"""
        if self.driver:
            return
        
        try:
            options = uc.ChromeOptions()
            
            if self.headless:
                options.add_argument('--headless=new')
            
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            self.driver = uc.Chrome(options=options)
            self.driver.set_page_load_timeout(45)  # Увеличен timeout
            
            self.logger.info("✅ Chrome драйвер инициализирован")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации: {e}")
            raise
    
    def search(self, site: str, query: str, max_products: int = 20) -> List[Product]:
        """
        Поиск товаров на указанном сайте
        
        Args:
            site: домен сайта (например, 'mr-moto.ru')
            query: поисковый запрос
            max_products: максимальное количество товаров
        """
        products = []
        
        try:
            self._init_driver()
            
            # Получаем конфигурацию сайта
            config = self.SITES_CONFIG.get(site)
            
            if not config:
                self.logger.warning(f"⚠️ Конфигурация для {site} не найдена. Используем универсальный подход.")
                config = {
                    'search_url': f'https://{site}/search?q={{query}}',
                    'product_card_selectors': ['div.product', 'div.item', 'article'],
                    'title_selectors': ['h3', 'h2', 'a.title', 'a.name'],
                    'price_selectors': ['span.price', 'div.price', 'span.cost'],
                }
            
            # Формируем URL
            search_url = config['search_url'].format(query=quote_plus(query))
            
            self.logger.info(f"🔍 Поиск на {site}: {query}")
            self.logger.info(f"📍 URL: {search_url}")
            
            self.driver.get(search_url)
            
            # Ждем загрузки
            time.sleep(random.uniform(2, 4))
            
            # Прокручиваем
            self._scroll_page()
            
            # Парсим
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Ищем карточки товаров
            cards = self._find_product_cards(soup, config.get('product_card_selectors', []))
            
            self.logger.info(f"📦 Найдено карточек: {len(cards)}")
            
            for card in cards[:max_products]:
                try:
                    product = self._parse_product_card(card, config, site)
                    if product:
                        products.append(product)
                except Exception as e:
                    self.logger.debug(f"Ошибка парсинга: {e}")
                    continue
            
            self.logger.info(f"✅ Успешно спарсено: {len(products)} товаров")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка поиска: {e}")
        
        return products
    
    def _find_product_cards(self, soup, selectors):
        """Ищет карточки товаров по списку селекторов"""
        for selector in selectors or []:
            cards = []
            try:
                cards = soup.select(selector)
            except Exception:
                # Падаем обратно на find_all для простых селекторов
                if '.' in selector:
                    tag, class_name = selector.split('.', 1)
                    cards = soup.find_all(tag, class_=lambda x: x and class_name in str(x))
                else:
                    cards = soup.find_all(selector)
            if cards:
                return cards
        
        # Если ничего не найдено, ищем универсально
        cards = soup.find_all('div', class_=lambda x: x and any(
            word in str(x).lower() for word in ['product', 'item', 'goods', 'catalog']
        ))
        
        return cards
    
    def _extract_value_by_selectors(self, node, selectors):
        """Возвращает текст/атрибут первого подходящего элемента по списку селекторов"""
        if not selectors:
            return ""
        
        for selector in selectors:
            attr = 'text'
            css = selector
            if isinstance(selector, dict):
                css = selector.get('selector')
                attr = selector.get('attr', 'text')
            if not css:
                continue
            try:
                element = node.select_one(css)
            except Exception:
                element = None
            if not element:
                continue
            
            if attr == 'text':
                value = element.get_text(strip=True)
            else:
                value = element.get(attr)
            
            if value:
                return str(value).strip()
        
        return ""
    
    def _scroll_page(self):
        """Прокручивает страницу"""
        try:
            for i in range(2):
                self.driver.execute_script(f"window.scrollTo(0, {1000 * (i + 1)});")
                time.sleep(1)
            
            self.driver.execute_script("window.scrollTo(0, 300);")
            time.sleep(0.5)
            
        except Exception as e:
            self.logger.debug(f"Ошибка прокрутки: {e}")
    
    def _parse_product_card(self, card, config, site) -> Optional[Product]:
        """Парсит карточку товара"""
        try:
            # Ссылка на товар
            link = card.find('a', href=True)
            if not link:
                return None
            
            href = link.get('href', '')
            if not href.startswith('http'):
                href = f"https://{site}{href if href.startswith('/') else '/' + href}"
            
            product_url = href.split('?')[0]
            
            # Название
            title = self._extract_value_by_selectors(card, config.get('title_selectors'))
            if not title:
                title = link.get('title', '') or link.get_text(strip=True)
            
            if not title or len(title) < 3:
                return None
            
            # Бренд (опционально)
            brand = self._extract_value_by_selectors(card, config.get('brand_selectors'))
            
            # Цена
            price = 0.0
            old_price = None
            price_text = self._extract_value_by_selectors(card, config.get('price_selectors'))
            if price_text:
                price = self._extract_price(price_text)
            
            # Если цена не найдена, ищем любой текст с рублями
            if price == 0:
                price_elem = card.find(string=lambda x: x and '₽' in str(x))
                if price_elem:
                    price = self._extract_price(price_elem)
            
            # Изображение
            image_url = ""
            img = card.find('img')
            if img:
                image_url = img.get('src', '') or img.get('data-src', '')
                if image_url and not image_url.startswith('http'):
                    image_url = f"https://{site}{image_url}"
            
            if price > 0:
                return Product(
                    title=title[:200],
                    price=price,
                    old_price=old_price,
                    url=product_url,
                    source=site,
                    availability="in_stock",
                    brand=brand or "",
                    image_url=image_url
                )
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Ошибка парсинга карточки: {e}")
            return None
    
    def _extract_price(self, price_text: str) -> float:
        """Извлекает цену"""
        if not price_text:
            return 0.0
        
        text = str(price_text).replace('\xa0', '').replace(' ', '')
        match = re.search(r'(\d+[.,]?\d*)', text)
        if not match:
            return 0.0
        
        number_str = match.group(1).replace(',', '.')
        try:
            return float(number_str)
        except Exception:
            return 0.0
    
    def close(self):
        """Закрывает браузер"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("🔒 Браузер закрыт")
            except (OSError, Exception) as e:
                # Игнорируем ошибки с дескрипторами при закрытии
                if "WinError 6" not in str(e):
                    self.logger.debug(f"Ошибка при закрытии браузера: {e}")
            finally:
                self.driver = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Тестирование
if __name__ == "__main__":
    print("=" * 80)
    print("  ТЕСТ УНИВЕРСАЛЬНОГО SCRAPER")
    print("=" * 80)
    print()
    
    with UniversalScraper(headless=False) as scraper:
        # Тестируем на разных сайтах
        sites = ['mr-moto.ru', 'flipup.ru']
        query = "мотошлем"
        
        for site in sites:
            print(f"\n🔍 Сайт: {site}")
            print(f"   Запрос: '{query}'")
            print("-" * 80)
            
            products = scraper.search(site, query, max_products=3)
            
            if products:
                print(f"\n✅ Найдено: {len(products)} товаров\n")
                
                for i, product in enumerate(products, 1):
                    print(f"{i}. {product.title[:60]}...")
                    print(f"   💰 Цена: {product.price:,.0f}₽")
                    print(f"   🔗 {product.url}\n")
            else:
                print("\n⚠️ Товары не найдены")
            
            time.sleep(2)
    
    print("=" * 80)
    print("  ✅ Тестирование завершено")
    print("=" * 80)
