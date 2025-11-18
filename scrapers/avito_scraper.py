"""
Selenium скрапер для Avito
На основе детального отчета по парсингу Avito
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
from urllib.parse import quote
import random

@dataclass
class Product:
    title: str
    price: float
    old_price: Optional[float] = None
    url: str = ""
    source: str = "Avito"
    availability: str = "unknown"
    location: str = ""
    seller: str = ""
    image_url: str = ""
    reviews_count: int = 0
    rating: float = 0.0


class AvitoScraper:
    """Selenium скрапер для Avito"""
    
    def __init__(self, headless: bool = True, city: str = "rossiya"):
        self.headless = headless
        self.city = city  # rossiya, moskva, sankt-peterburg и т.д.
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
            self.driver.set_page_load_timeout(60)  # Увеличен timeout для Avito (часто медленный)
            
            self.logger.info("✅ Chrome драйвер инициализирован")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации: {e}")
            raise
    
    def search(self, query: str, max_products: int = 20) -> List[Product]:
        """Поиск товаров на Avito"""
        products = []
        
        try:
            self._init_driver()
            
            # Avito URL: https://www.avito.ru/{город}?q={запрос}
            search_url = f"https://www.avito.ru/{self.city}?q={quote(query)}"
            
            self.logger.info(f"🔍 Поиск на Avito: {query}")
            self.logger.info(f"📍 URL: {search_url}")
            
            self.driver.get(search_url)
            
            # Ждем загрузки
            time.sleep(random.uniform(3, 5))
            
            # Прокручиваем
            self._scroll_page()
            
            # Парсим
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Avito использует data-marker для элементов
            cards = soup.find_all(attrs={'data-marker': 'item'})
            
            if not cards:
                # Альтернативный поиск
                cards = soup.find_all('div', class_=lambda x: x and 'item' in str(x).lower())
            
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
        """Прокручивает страницу"""
        try:
            for i in range(3):
                self.driver.execute_script(f"window.scrollTo(0, {1000 * (i + 1)});")
                time.sleep(1.5)
            
            self.driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(1)
            
        except Exception as e:
            pass
    
    def _parse_product_card(self, card) -> Optional[Product]:
        """
        Парсит карточку товара Avito
        
        Структура:
        - data-marker="item-title" - название
        - data-marker="item-price" - цена
        - href содержит ссылку на товар
        """
        try:
            # Ссылка
            link = card.find('a', attrs={'data-marker': 'item-title'})
            if not link:
                link = card.find('a', href=lambda x: x and '/items/' in str(x))
            
            if not link:
                return None
            
            href = link.get('href', '')
            if not href.startswith('http'):
                href = f"https://www.avito.ru{href}"
            
            product_url = href.split('?')[0]
            
            # Название
            title = link.get('title', '') or link.get_text(strip=True)
            
            if not title or len(title) < 5:
                title_elem = card.find(attrs={'data-marker': 'item-title'})
                if title_elem:
                    title = title_elem.get_text(strip=True)
            
            if not title or len(title) < 5:
                return None
            
            # Цена
            price = 0.0
            price_elem = card.find(attrs={'data-marker': 'item-price'})
            
            if not price_elem:
                price_elem = card.find(string=lambda x: x and '₽' in str(x))
            
            if price_elem:
                price_text = price_elem if isinstance(price_elem, str) else price_elem.get_text(strip=True)
                price = self._extract_price(price_text)
            
            # Местоположение
            location = ""
            location_elem = card.find(attrs={'data-marker': 'item-address'})
            if location_elem:
                location = location_elem.get_text(strip=True)
            
            # Продавец
            seller = ""
            seller_elem = card.find(attrs={'data-marker': 'seller-info'})
            if seller_elem:
                seller = seller_elem.get_text(strip=True)

            # Количество отзывов
            reviews_count = 0
            reviews_elem = card.find(attrs={'data-marker': 'seller-info/summary'})
            if reviews_elem:
                reviews_text = reviews_elem.get_text(strip=True)
                reviews_match = re.search(r'(\d[\d\s]*)', reviews_text)
                if reviews_match:
                    try:
                        reviews_count = int(re.sub(r'\s+', '', reviews_match.group(1)))
                    except ValueError:
                        reviews_count = 0

            # Рейтинг продавца
            rating = 0.0
            rating_elem = card.find(attrs={'data-marker': 'seller-rating/score'})
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True).replace(',', '.')
                try:
                    rating = float(re.sub(r'[^\d\.]', '', rating_text))
                except ValueError:
                    rating = 0.0

            # Фильтрация продавцов с отзывами < 50
            if reviews_count < 50:
                return None
            
            # Изображение
            image_url = ""
            img = card.find('img')
            if img:
                image_url = img.get('src', '') or img.get('data-src', '')
            
            if price > 0:
                return Product(
                    title=title[:200],
                    price=price,
                    url=product_url,
                    source="Avito",
                    availability="in_stock",
                    location=location,
                    seller=seller,
                    image_url=image_url,
                    reviews_count=reviews_count,
                    rating=rating
                )
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Ошибка парсинга карточки: {e}")
            return None
    
    def _extract_price(self, price_text: str) -> float:
        """Извлекает цену"""
        if not price_text:
            return 0.0
        
        # Убираем все кроме цифр
        clean_text = re.sub(r'[^\d]', '', str(price_text))
        
        try:
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
                    pass
            finally:
                self.driver = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Тестирование
if __name__ == "__main__":
    print("=" * 80)
    print("  ТЕСТ AVITO SCRAPER")
    print("=" * 80)
    print()
    
    with AvitoScraper(headless=False, city="rossiya") as scraper:
        queries = ["мотошлем HJC", "мотоэкипировка"]
        
        for query in queries:
            print(f"\n🔍 Поиск: '{query}'")
            print("-" * 80)
            
            products = scraper.search(query, max_products=5)
            
            if products:
                print(f"\n✅ Найдено: {len(products)} товаров\n")
                
                for i, product in enumerate(products, 1):
                    print(f"{i}. {product.title[:60]}...")
                    print(f"   💰 Цена: {product.price:,.0f}₽")
                    if product.location:
                        print(f"   📍 Место: {product.location}")
                    print(f"   🔗 {product.url}\n")
            else:
                print("\n⚠️ Товары не найдены")
            
            time.sleep(2)
    
    print("=" * 80)
    print("  ✅ Тестирование завершено")
    print("=" * 80)
