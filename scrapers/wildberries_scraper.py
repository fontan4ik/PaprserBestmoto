"""
Selenium скрапер для Wildberries
На основе детального отчета по инспекции сайта
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import time
import re
import logging
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import quote
import random

@dataclass
class Product:
    title: str
    price: float
    old_price: Optional[float] = None
    url: str = ""
    source: str = "Wildberries"
    availability: str = "unknown"
    brand: str = ""
    rating: float = 0.0
    reviews_count: int = 0
    image_url: str = ""


class WildberriesScraper:
    """
    Selenium скрапер для Wildberries
    Обходит Cloudflare и корректно извлекает данные
    """
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
    
    def _init_driver(self):
        """Инициализация Chrome драйвера с обходом детектирования"""
        if self.driver:
            return
        
        try:
            options = uc.ChromeOptions()
            
            if self.headless:
                options.add_argument('--headless=new')
            
            # Настройки для обхода детектирования
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            self.driver = uc.Chrome(options=options)
            self.driver.set_page_load_timeout(45)  # Увеличен timeout
            
            self.logger.info("✅ Chrome драйвер инициализирован")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации драйвера: {e}")
            raise
    
    def search(self, query: str, max_products: int = 20) -> List[Product]:
        """
        Поиск товаров на Wildberries
        
        Args:
            query: поисковый запрос
            max_products: максимальное количество товаров
        
        Returns:
            список найденных товаров
        """
        products = []
        
        try:
            self._init_driver()
            
            # Формируем URL поиска
            search_url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={quote(query)}"
            
            self.logger.info(f"🔍 Поиск на Wildberries: {query}")
            self.logger.info(f"📍 URL: {search_url}")
            
            # Открываем страницу
            self.driver.get(search_url)
            
            # Ждем загрузки (обход Cloudflare)
            time.sleep(random.uniform(3, 5))
            
            # Прокручиваем для загрузки товаров
            self._scroll_page()
            
            # Парсим страницу
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Ищем карточки товаров
            # Wildberries использует data-nm-id для идентификации товаров
            cards = soup.find_all('article', class_='product-card')
            
            if not cards:
                # Альтернативный поиск
                cards = soup.find_all('div', {'data-nm-id': True})
            
            self.logger.info(f"📦 Найдено карточек: {len(cards)}")
            
            for card in cards[:max_products]:
                try:
                    product = self._parse_product_card(card)
                    if product:
                        products.append(product)
                except Exception as e:
                    self.logger.debug(f"Ошибка парсинга карточки: {e}")
                    continue
            
            self.logger.info(f"✅ Успешно спарсено: {len(products)} товаров")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка поиска: {e}")
        
        return products
    
    def _scroll_page(self):
        """Прокручивает страницу для загрузки товаров"""
        try:
            # Прокручиваем постепенно
            scroll_pause = 1.5
            scroll_height = 1000
            
            for i in range(3):
                self.driver.execute_script(f"window.scrollTo(0, {scroll_height * (i + 1)});")
                time.sleep(scroll_pause)
            
            # Возвращаемся наверх
            self.driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(1)
            
        except Exception as e:
            self.logger.debug(f"Ошибка прокрутки: {e}")
    
    def _parse_product_card(self, card) -> Optional[Product]:
        """
        Парсит карточку товара
        
        Структура Wildberries:
        - data-nm-id: ID товара
        - product-card__name: название
        - price__lower-price: цена со скидкой
        - price__del: старая цена
        - product-card__brand: бренд
        """
        try:
            # ID товара
            product_id = card.get('data-nm-id')
            if not product_id:
                # Ищем в дочерних элементах
                id_elem = card.find(attrs={'data-nm-id': True})
                product_id = id_elem.get('data-nm-id') if id_elem else None
            
            if not product_id:
                return None
            
            # Название
            name_elem = card.find(class_=re.compile('product-card__name|goods-name'))
            title = name_elem.get_text(strip=True) if name_elem else ""
            
            # Бренд
            brand_elem = card.find(class_=re.compile('product-card__brand|brand-name'))
            brand = brand_elem.get_text(strip=True) if brand_elem else ""
            
            # Полное название
            if brand and title:
                full_title = f"{brand} {title}"
            else:
                full_title = title or brand
            
            if not full_title:
                return None
            
            # Цена
            price = 0.0
            old_price = None
            
            # Цена со скидкой
            price_elem = card.find(class_=re.compile('price__lower-price|price-current'))
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._extract_price(price_text)
            
            # Старая цена
            old_price_elem = card.find(class_=re.compile('price__del|price-old'))
            if old_price_elem:
                old_price_text = old_price_elem.get_text(strip=True)
                old_price = self._extract_price(old_price_text)
            
            # URL товара
            product_url = f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx"
            
            # Рейтинг продавца
            rating = 0.0
            # Ищем по конкретному классу: address-rate-mini address-rate-mini--sm
            rating_elem = card.find('span', class_=re.compile('address-rate-mini'))
            if not rating_elem:
                # Альтернативный поиск
                rating_elem = card.find(class_=re.compile('address-rate-mini|product-card__rating|rating'))
            
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                try:
                    # Заменяем запятую на точку для парсинга (4,1 -> 4.1)
                    rating_text_clean = rating_text.replace(',', '.')
                    rating_match = re.search(r'(\d+\.?\d*)', rating_text_clean)
                    if rating_match:
                        rating = float(rating_match.group(1))
                except:
                    pass
            
            # Количество отзывов
            reviews_count = 0
            # Ищем по конкретному классу: product-card__count
            reviews_elem = card.find('span', class_='product-card__count')
            if not reviews_elem:
                # Альтернативный поиск
                reviews_elem = card.find(class_=re.compile('product-card__count|reviews-count'))
            
            if reviews_elem:
                reviews_text = reviews_elem.get_text(strip=True)
                try:
                    # Извлекаем число из текста типа "7 оценок"
                    reviews_match = re.search(r'(\d+)', reviews_text.replace(' ', ''))
                    if reviews_match:
                        reviews_count = int(reviews_match.group(1))
                except:
                    pass
            
            # Изображение
            image_url = ""
            img_elem = card.find('img')
            if img_elem:
                image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
            
            if price > 0:
                return Product(
                    title=full_title,
                    price=price,
                    old_price=old_price,
                    url=product_url,
                    source="Wildberries",
                    availability="in_stock",
                    brand=brand,
                    rating=rating,
                    reviews_count=reviews_count,
                    image_url=image_url
                )
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Ошибка парсинга карточки: {e}")
            return None
    
    def _extract_price(self, price_text: str) -> float:
        """Извлекает цену из текста"""
        if not price_text:
            return 0.0
        
        # Убираем все кроме цифр
        clean_text = re.sub(r'[^\d]', '', price_text)
        
        try:
            # Цена в рублях
            return float(clean_text) if clean_text else 0.0
        except:
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
    print("  ТЕСТ WILDBERRIES SCRAPER")
    print("=" * 80)
    print()
    
    with WildberriesScraper(headless=False) as scraper:
        # Тестовые запросы
        queries = ["HJC RPHA71", "мотошлем"]
        
        for query in queries:
            print(f"\n🔍 Поиск: '{query}'")
            print("-" * 80)
            
            products = scraper.search(query, max_products=5)
            
            if products:
                print(f"\n✅ Найдено: {len(products)} товаров\n")
                
                for i, product in enumerate(products, 1):
                    print(f"{i}. {product.title}")
                    print(f"   💰 Цена: {product.price:,.0f}₽", end="")
                    if product.old_price:
                        print(f" (было {product.old_price:,.0f}₽)")
                    else:
                        print()
                    print(f"   ⭐ Рейтинг: {product.rating} ({product.reviews_count} отзывов)")
                    print(f"   🔗 {product.url}\n")
            else:
                print("\n⚠️ Товары не найдены")
            
            time.sleep(2)
    
    print("=" * 80)
    print("  ✅ Тестирование завершено")
    print("=" * 80)
