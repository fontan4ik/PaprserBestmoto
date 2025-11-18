"""
Selenium скрапер для OZON
На основе подробного отчета по парсингу OZON.RU
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
    source: str = "OZON"
    availability: str = "unknown"
    brand: str = ""
    rating: float = 0.0
    reviews_count: int = 0
    image_url: str = ""


class OzonScraper:
    """Selenium скрапер для OZON"""
    
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
    
    def search(self, query: str, max_products: int = 20) -> List[Product]:
        """Поиск товаров на OZON"""
        products = []
        
        try:
            self._init_driver()
            
            search_url = f"https://www.ozon.ru/search/?text={quote(query)}"
            
            self.logger.info(f"🔍 Поиск на OZON: {query}")
            self.logger.info(f"📍 URL: {search_url}")
            
            self.driver.get(search_url)
            
            # Ждем загрузки
            time.sleep(random.uniform(4, 6))
            
            # Прокручиваем
            self._scroll_page()
            
            # Сначала пробуем извлечь через Selenium (более надежно для динамического контента)
            try:
                # Ищем карточки товаров через Selenium
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                
                # Ждем загрузки результатов
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/product/']"))
                )
                
                # Ищем все ссылки на товары
                product_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/product/']")
                
                seen_urls = set()
                for link_elem in product_links[:max_products * 2]:
                    try:
                        href = link_elem.get_attribute('href')
                        if not href or href in seen_urls:
                            continue
                        seen_urls.add(href)
                        
                        # Пробуем извлечь название через Selenium
                        title = ""
                        try:
                            # Метод 1: Атрибут title ссылки
                            title = link_elem.get_attribute('title') or ""
                            
                            # Метод 2: Текст ссылки
                            if not title or len(title) < 10:
                                title = link_elem.text.strip()
                            
                            # Метод 3: Ищем в родительском элементе span с классом tsBody
                            if not title or len(title) < 10:
                                try:
                                    parent = link_elem.find_element(By.XPATH, "./ancestor::div[1]")
                                    title_spans = parent.find_elements(By.CSS_SELECTOR, "span[class*='tsBody'], span[class*='title'], span[class*='name']")
                                    for span in title_spans:
                                        span_text = span.text.strip()
                                        # Более строгая фильтрация мусорных текстов
                                        if (len(span_text) > 15 and 
                                            'шт' not in span_text.lower() and 
                                            'распродажа' not in span_text.lower() and
                                            'цена что надо' not in span_text.lower() and
                                            '₽' not in span_text and
                                            not re.match(r'^\d+$', span_text) and
                                            not re.match(r'^\d+\.\d+$', span_text) and
                                            not span_text.lower().startswith('остал') and
                                            not span_text.lower().startswith('распродажа')):
                                            if len(span_text) > len(title):
                                                title = span_text
                                except:
                                    pass
                            
                            # Метод 4: Ищем в родительском контейнере карточки товара
                            if not title or len(title) < 10:
                                try:
                                    # Ищем карточку товара (обычно это div с классом tile или содержащий data-widget)
                                    card_container = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'tile') or contains(@data-widget, 'search')][1]")
                                    
                                    # Ищем все span элементы в карточке
                                    all_spans = card_container.find_elements(By.TAG_NAME, "span")
                                    for span in all_spans:
                                        span_text = span.text.strip()
                                        # Проверяем, что это не служебный текст
                                        if (len(span_text) > 20 and 
                                            len(span_text) < 200 and  # Не слишком длинные (описания)
                                            'шт' not in span_text.lower() and 
                                            'распродажа' not in span_text.lower() and
                                            'цена что надо' not in span_text.lower() and
                                            '₽' not in span_text and
                                            not re.match(r'^\d+$', span_text) and
                                            not re.match(r'^\d+\.\d+$', span_text) and
                                            not span_text.lower().startswith('остал') and
                                            not span_text.lower().startswith('распродажа') and
                                            not span_text.lower().startswith('цена') and
                                            # Проверяем, что это похоже на название товара (содержит буквы)
                                            re.search(r'[а-яёА-ЯЁa-zA-Z]', span_text)):
                                            if len(span_text) > len(title):
                                                title = span_text
                                except:
                                    pass
                        except Exception as e:
                            pass
                        
                        # Если название не найдено через Selenium, используем BeautifulSoup
                        if not title or len(title) < 10:
                            try:
                                # Получаем HTML карточки для парсинга
                                card_html = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'tile') or contains(@data-widget, 'search')][1]")
                                card_html_source = card_html.get_attribute('outerHTML')
                                soup_card = BeautifulSoup(card_html_source, 'html.parser')
                                product = self._parse_product_card(soup_card, href=href)
                            except Exception as e:
                                product = None
                        else:
                            # Очищаем название от мусорных фраз
                            title = re.sub(r'\s*остал[а-яё]*\s*\d+\s*шт\s*', '', title, flags=re.IGNORECASE)
                            title = re.sub(r'\s*распродажа\s*\d+\.\d+\.\d+\s*', '', title, flags=re.IGNORECASE)
                            title = re.sub(r'\s*цена\s*что\s*надо\s*', '', title, flags=re.IGNORECASE)
                            title = re.sub(r'\s*остал[а-яё]*\s*\d+\s*шт\s*распродажа\s*', '', title, flags=re.IGNORECASE)
                            title = re.sub(r'распродажа\s*\d+\.\d+\.\d+\s*', '', title, flags=re.IGNORECASE)
                            title = title.strip()
                            
                            # Если название все еще содержит мусор, пропускаем
                            if (len(title) < 10 or 
                                title.lower().startswith('остал') or 
                                title.lower().startswith('распродажа') or
                                'штраспродажа' in title.lower() or
                                re.match(r'^\d+\s*шт', title, flags=re.IGNORECASE)):
                                product = None
                            else:
                                # Извлекаем цену
                                price = 0.0
                                try:
                                    parent = link_elem.find_element(By.XPATH, "./ancestor::div[1]")
                                    # Ищем все элементы с текстом, содержащим ₽
                                    all_elems = parent.find_elements(By.XPATH, ".//*[contains(text(), '₽')]")
                                    for price_elem in all_elems:
                                        price_text = price_elem.text
                                        if '₽' in price_text:
                                            price = self._extract_price(price_text)
                                            if price > 0:
                                                break
                                    # Если не нашли, ищем по классам с price
                                    if price == 0:
                                        price_elems = parent.find_elements(By.CSS_SELECTOR, "*[class*='price'], *[class*='cost']")
                                        for price_elem in price_elems:
                                            price_text = price_elem.text
                                            if '₽' in price_text:
                                                price = self._extract_price(price_text)
                                                if price > 0:
                                                    break
                                except Exception as e:
                                    pass
                                
                                # Парсим рейтинг и отзывы
                                rating = 0.0
                                reviews_count = 0
                                try:
                                    parent = link_elem.find_element(By.XPATH, "./ancestor::div[1]")
                                    
                                    # Рейтинг: ищем span со стилем color:var(--textPremium)
                                    try:
                                        rating_elems = parent.find_elements(By.CSS_SELECTOR, "span[style*='textPremium']")
                                        for rating_elem in rating_elems:
                                            rating_text = rating_elem.text.strip()
                                            rating_match = re.search(r'(\d+\.\d+)', rating_text)
                                            if rating_match:
                                                rating = float(rating_match.group(1))
                                                # Если рейтинг больше 5.0, считаем его невалидным (0)
                                                if rating > 5.0:
                                                    rating = 0.0
                                                break
                                    except:
                                        pass
                                    
                                    # Отзывы: ищем span с классом p6b3_0_4-a4
                                    try:
                                        reviews_elems = parent.find_elements(By.CSS_SELECTOR, "span.p6b3_0_4-a4")
                                        for reviews_elem in reviews_elems:
                                            # Ищем внутри span с текстом
                                            inner_spans = reviews_elem.find_elements(By.TAG_NAME, "span")
                                            for inner_span in inner_spans:
                                                reviews_text = inner_span.text.strip()
                                                if 'отзыв' in reviews_text.lower() or 'оценок' in reviews_text.lower():
                                                    reviews_match = re.search(r'(\d+)', reviews_text.replace(' ', '').replace('\xa0', ''))
                                                    if reviews_match:
                                                        reviews_count = int(reviews_match.group(1))
                                                        break
                                            if reviews_count > 0:
                                                break
                                    except:
                                        pass
                                except Exception as e:
                                    pass
                                
                                if title and len(title) > 5 and price > 0:
                                    product = Product(
                                        title=title[:200],
                                        price=price,
                                        url=href.split('?')[0] if '?' in href else href,
                                        source="OZON",
                                        availability="in_stock",
                                        rating=rating,
                                        reviews_count=reviews_count
                                    )
                                else:
                                    product = None
                        
                        if product:
                            products.append(product)
                    
                    except Exception as e:
                        pass
            
            except Exception as e:
                pass
            
            # Если через Selenium ничего не нашли, используем BeautifulSoup (старый метод)
            if len(products) == 0:
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # OZON использует разные классы для карточек
                cards = soup.find_all('div', {'data-widget': 'searchResultsV2'})
                
                if not cards:
                    # Альтернативный поиск
                    cards = soup.find_all('div', class_=lambda x: x and 'tile' in str(x).lower())
                
                if not cards:
                    # Ищем по ссылкам на товары
                    links = soup.find_all('a', href=lambda x: x and '/product/' in str(x))
                    
                    # Группируем по родительским элементам
                    seen_urls = set()
                    for link in links[:max_products * 2]:
                        try:
                            # Получаем родительский контейнер
                            parent = link.parent
                            for _ in range(5):
                                if parent and parent.parent:
                                    parent = parent.parent
                            
                            if parent and parent not in cards:
                                href = link.get('href', '')
                                if href and href not in seen_urls:
                                    cards.append(parent)
                                    seen_urls.add(href)
                        except:
                            continue
                
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
    
    def _parse_product_card(self, card, href: str = None) -> Optional[Product]:
        """
        Парсит карточку товара OZON
        
        Структура:
        - Ссылка содержит /product/название-ID/
        - Название в тексте ссылки или в title
        - Цена в элементах с классами price/cost
        """
        try:
            # Ссылка на товар
            link = card.find('a', href=lambda x: x and '/product/' in str(x))
            if not link:
                return None
            
            href = link.get('href', '')
            if not href.startswith('http'):
                href = f"https://www.ozon.ru{href}"
            
            # Очищаем URL от параметров
            product_url = href.split('?')[0]
            
            # Название - ищем более точно
            title = ""
            
            # Метод 1: Ищем в span с data-widget="searchResultsV2" или в дочерних элементах
            # Ozon часто использует структуру: span > текст названия
            title_spans = card.find_all('span', recursive=True)
            for span in title_spans:
                span_text = span.get_text(strip=True)
                # Более строгая фильтрация: пропускаем короткие тексты и служебные (остатки, акции, цены)
                if (len(span_text) > 20 and 
                    len(span_text) < 200 and  # Не слишком длинные (описания)
                    'шт' not in span_text.lower() and 
                    'распродажа' not in span_text.lower() and 
                    'цена что надо' not in span_text.lower() and
                    '₽' not in span_text and
                    not re.match(r'^\d+$', span_text) and
                    not re.match(r'^\d+\.\d+$', span_text) and
                    not span_text.lower().startswith('остал') and
                    not span_text.lower().startswith('распродажа') and
                    not span_text.lower().startswith('цена') and
                    'штраспродажа' not in span_text.lower() and
                    # Проверяем, что это похоже на название товара (содержит буквы)
                    re.search(r'[а-яёА-ЯЁa-zA-Z]', span_text)):
                    if len(span_text) > len(title):
                        title = span_text
            
            # Метод 2: Ищем в ссылке (title атрибут или текст)
            if not title or len(title) < 10:
                link_title = link.get('title', '')
                link_text = link.get_text(strip=True)
                # Выбираем более длинный и осмысленный текст
                if link_title and len(link_title) > 15 and 'шт' not in link_title.lower():
                    title = link_title
                elif link_text and len(link_text) > 15 and 'шт' not in link_text.lower():
                    title = link_text
            
            # Метод 3: Ищем в div с классами, содержащими "title", "name", "product"
            if not title or len(title) < 10:
                for tag in ['div', 'span', 'h3', 'h4', 'a']:
                    elems = card.find_all(tag, class_=lambda x: x and any(
                        word in str(x).lower() for word in ['title', 'name', 'product', 'card']
                    ))
                    for elem in elems:
                        elem_text = elem.get_text(strip=True)
                        if (len(elem_text) > 15 and 
                            'шт' not in elem_text.lower() and
                            'распродажа' not in elem_text.lower() and
                            '₽' not in elem_text):
                            if len(elem_text) > len(title):
                                title = elem_text
                                break
            
            # Метод 4: Ищем все текстовые элементы и выбираем самый длинный осмысленный
            if not title or len(title) < 10:
                all_texts = card.find_all(string=True, recursive=True)
                for text in all_texts:
                    text_clean = text.strip()
                    if (len(text_clean) > 20 and 
                        'шт' not in text_clean.lower() and
                        'распродажа' not in text_clean.lower() and
                        'цена что надо' not in text_clean.lower() and
                        '₽' not in text_clean and
                        not re.match(r'^\d+$', text_clean) and
                        not re.match(r'^\d+\.\d+$', text_clean)):
                        if len(text_clean) > len(title):
                            title = text_clean
            
            # Очищаем название от мусора
            if title:
                # Убираем служебные фразы
                title = re.sub(r'\s*остал[а-яё]*\s*\d+\s*шт\s*', '', title, flags=re.IGNORECASE)
                title = re.sub(r'\s*распродажа\s*\d+\.\d+\.\d+\s*', '', title, flags=re.IGNORECASE)
                title = re.sub(r'\s*цена\s*что\s*надо\s*', '', title, flags=re.IGNORECASE)
                title = re.sub(r'\s*остал[а-яё]*\s*\d+\s*шт\s*распродажа\s*', '', title, flags=re.IGNORECASE)
                title = re.sub(r'распродажа\s*\d+\.\d+\.\d+\s*', '', title, flags=re.IGNORECASE)
                title = title.strip()
            
            # Финальная проверка: если название все еще содержит мусор, пропускаем
            if (not title or 
                len(title) < 10 or 
                title.lower().startswith('остал') or 
                title.lower().startswith('распродажа') or
                'штраспродажа' in title.lower() or
                re.match(r'^\d+\s*шт', title, flags=re.IGNORECASE)):
                return None
            
            # Цена
            price = 0.0
            old_price = None
            
            # Ищем цену
            price_elem = card.find(['span', 'div'], string=lambda x: x and '₽' in str(x))
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._extract_price(price_text)
            
            # Альтернативный поиск цены
            if price == 0:
                price_elems = card.find_all(string=lambda x: x and '₽' in str(x))
                for elem in price_elems:
                    p = self._extract_price(elem)
                    if p > 0:
                        if price == 0:
                            price = p
                        elif p < price:
                            old_price = price
                            price = p
                        elif p > price:
                            old_price = p
            
            # Рейтинг продавца
            rating = 0.0
            # Ищем span со стилем color:var(--textPremium)
            rating_elem = card.find('span', style=lambda x: x and 'textPremium' in str(x) if x else False)
            if not rating_elem:
                # Альтернативный поиск по тексту с рейтингом
                rating_elem = card.find(string=lambda x: x and re.search(r'\d+\.\d+', str(x)))
            
            if rating_elem:
                try:
                    if isinstance(rating_elem, str):
                        rating_text = rating_elem
                    else:
                        rating_text = rating_elem.get_text(strip=True)
                    rating_match = re.search(r'(\d+\.\d+)', rating_text)
                    if rating_match:
                        rating = float(rating_match.group(1))
                        # Если рейтинг больше 5.0, считаем его невалидным (0)
                        if rating > 5.0:
                            rating = 0.0
                except:
                    pass
            
            # Количество отзывов
            reviews_count = 0
            # Ищем span с классом p6b3_0_4-a4
            reviews_elem = card.find('span', class_='p6b3_0_4-a4')
            if reviews_elem:
                # Ищем внутри span с текстом типа "1 отзыв" или "7 оценок"
                reviews_span = reviews_elem.find('span', string=lambda x: x and ('отзыв' in str(x).lower() or 'оценок' in str(x).lower()) if x else False)
                if not reviews_span:
                    # Ищем любой span внутри с числом
                    reviews_span = reviews_elem.find('span')
                
                if reviews_span:
                    reviews_text = reviews_span.get_text(strip=True)
                    try:
                        # Извлекаем число из текста типа "1 отзыв" или "7 оценок"
                        reviews_match = re.search(r'(\d+)', reviews_text.replace(' ', '').replace('\xa0', ''))
                        if reviews_match:
                            reviews_count = int(reviews_match.group(1))
                    except:
                        pass
            
            # Изображение
            image_url = ""
            img = card.find('img')
            if img:
                image_url = img.get('src', '') or img.get('data-src', '')
            
            if price > 0:
                return Product(
                    title=title[:200],
                    price=price,
                    old_price=old_price,
                    url=product_url,
                    source="OZON",
                    availability="in_stock",
                    rating=rating,
                    reviews_count=reviews_count,
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
    print("  ТЕСТ OZON SCRAPER")
    print("=" * 80)
    print()
    
    with OzonScraper(headless=False) as scraper:
        queries = ["HJC RPHA71", "мотошлем"]
        
        for query in queries:
            print(f"\n🔍 Поиск: '{query}'")
            print("-" * 80)
            
            products = scraper.search(query, max_products=5)
            
            if products:
                print(f"\n✅ Найдено: {len(products)} товаров\n")
                
                for i, product in enumerate(products, 1):
                    print(f"{i}. {product.title[:60]}...")
                    print(f"   💰 Цена: {product.price:,.0f}₽", end="")
                    if product.old_price:
                        print(f" (было {product.old_price:,.0f}₽)")
                    else:
                        print()
                    if product.rating > 0:
                        print(f"   ⭐ Рейтинг: {product.rating}")
                    print(f"   🔗 {product.url}\n")
            else:
                print("\n⚠️ Товары не найдены")
            
            time.sleep(2)
    
    print("=" * 80)
    print("  ✅ Тестирование завершено")
    print("=" * 80)
