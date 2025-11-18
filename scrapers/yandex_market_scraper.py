"""
Selenium скрапер для Яндекс Маркет
На основе полной документации для парсера Яндекс Маркет
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
    source: str = "Яндекс Маркет"
    availability: str = "unknown"
    brand: str = ""
    rating: float = 0.0
    reviews_count: int = 0
    image_url: str = ""


class YandexMarketScraper:
    """Selenium скрапер для Яндекс Маркет"""
    
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
        """Поиск товаров на Яндекс Маркет"""
        products = []
        
        try:
            self._init_driver()
            
            # Яндекс Маркет URL
            search_url = f"https://market.yandex.ru/search?text={quote(query)}"
            
            self.logger.info(f"🔍 Поиск на Яндекс Маркет: {query}")
            self.logger.info(f"📍 URL: {search_url}")
            
            self.driver.get(search_url)
            
            # Ждем загрузки (Яндекс может показывать капчу)
            time.sleep(random.uniform(4, 6))
            
            # Проверяем капчу
            if "captcha" in self.driver.current_url.lower():
                self.logger.warning("⚠️ Обнаружена капча. Требуется ручное решение.")
                time.sleep(10)  # Даем время на решение
            
            # Прокручиваем
            self._scroll_page()
            
            # Сначала пробуем извлечь через Selenium (более надежно для динамического контента)
            try:
                # Ждем загрузки результатов - пробуем несколько селекторов
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.any_of(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/product/']")),
                            EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-auto]")),
                            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-zone-name='snippet-card']")),
                            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-zone-name*='snippet']"))
                        )
                    )
                except:
                    # Если не дождались, продолжаем - возможно элементы уже загружены
                    pass
                
                # Ищем ссылки на товары напрямую - пробуем разные варианты
                link_elements = []
                selectors = [
                    "a[href*='/product/']",
                    "a[href*='/card/']",
                    "a[href*='market.yandex.ru/product']",
                    "a[href*='/catalog']",
                    "article a[href*='/product']",
                    "article a[href*='/card']",
                    "[data-zone-name='snippet-card'] a",
                    "[data-zone-name='productSnippet'] a",
                    "[data-zone-name*='snippet'] a",
                    "[data-auto*='snippet'] a"
                ]
                
                for selector in selectors:
                    try:
                        found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if found:
                            link_elements.extend(found)
                    except:
                        continue
                
                # Убираем дубликаты
                seen_hrefs = set()
                unique_links = []
                for link in link_elements:
                    try:
                        href = link.get_attribute('href')
                        if href and href not in seen_hrefs and ('/product/' in href or '/card/' in href):
                            seen_hrefs.add(href)
                            unique_links.append(link)
                    except:
                        continue
                
                link_elements = unique_links
                
                if link_elements:
                    seen_urls = set()
                    # Ограничиваем количество ссылок для обработки (как в Ozon)
                    max_links_to_process = min(len(link_elements), max_products * 2)
                    for link_elem in link_elements[:max_links_to_process]:
                        # Проверяем лимит перед обработкой каждой ссылки
                        if len(products) >= max_products:
                            break
                        
                        try:
                            href = link_elem.get_attribute('href')
                            if not href or href in seen_urls:
                                continue
                            
                            # Нормализуем URL
                            if not href.startswith('http'):
                                href = f"https://market.yandex.ru{href}"
                            href = href.split('?')[0]
                            
                            if href in seen_urls:
                                continue
                            seen_urls.add(href)
                            
                            # Пробуем извлечь данные напрямую через Selenium
                            try:
                                # Название - пробуем несколько методов
                                title = ""
                                
                                # Метод 1: Атрибут title ссылки
                                title = link_elem.get_attribute('title') or ""
                                
                                # Метод 2: Текст ссылки
                                if not title or len(title) < 5:
                                    title = link_elem.text.strip()
                                
                                # Метод 3: Ищем в родительском элементе с data-auto="snippet-title"
                                if not title or len(title) < 5:
                                    try:
                                        # Пробуем найти родительский элемент разными способами
                                        parent = None
                                        try:
                                            parent = link_elem.find_element(By.XPATH, "./ancestor::article[1]")
                                        except:
                                            try:
                                                parent = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@data-zone-name, 'snippet')][1]")
                                            except:
                                                try:
                                                    parent = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'snippet')][1]")
                                                except:
                                                    parent = link_elem.find_element(By.XPATH, "./ancestor::*[contains(@class, 'card') or contains(@class, 'item')][1]")
                                        
                                        if parent:
                                            # Пробуем разные селекторы для названия
                                            title_selectors = [
                                                "[data-auto='snippet-title']",
                                                "[data-auto*='title']",
                                                "h3, h4, h2",
                                                ".snippet-title",
                                                ".product-title",
                                                "[class*='title']",
                                                "[class*='name']"
                                            ]
                                            for selector in title_selectors:
                                                try:
                                                    title_elems = parent.find_elements(By.CSS_SELECTOR, selector)
                                                    for elem in title_elems:
                                                        elem_text = elem.text.strip()
                                                        if len(elem_text) > 10 and len(elem_text) < 200:
                                                            title = elem_text
                                                            break
                                                    if title and len(title) > 5:
                                                        break
                                                except:
                                                    continue
                                    except Exception as e:
                                        pass
                                
                                # Метод 4: Ищем в родительском элементе любой длинный текст
                                if not title or len(title) < 5:
                                    try:
                                        parent = link_elem.find_element(By.XPATH, "./ancestor::article[1] | ./ancestor::div[contains(@data-zone-name, 'snippet')][1] | ./ancestor::div[contains(@class, 'snippet')][1]")
                                        # Получаем весь текст родительского элемента и ищем длинные фразы
                                        parent_text = parent.text
                                        # Разбиваем на строки и ищем самую длинную осмысленную
                                        lines = parent_text.split('\n')
                                        for line in lines:
                                            line = line.strip()
                                            if (len(line) > 15 and len(line) < 200 and
                                                '₽' not in line and
                                                not re.match(r'^\d+$', line) and
                                                not re.match(r'^\d+\.\d+$', line) and
                                                re.search(r'[а-яёА-ЯЁa-zA-Z]', line)):
                                                if len(line) > len(title):
                                                    title = line
                                    except:
                                        pass
                                
                                # Если название не найдено, пропускаем
                                if not title or len(title) < 5:
                                    continue
                                
                                # Цена - пробуем несколько методов
                                price = 0.0
                                
                                try:
                                    # Ищем родительский элемент карточки - пробуем разные способы
                                    parent = None
                                    try:
                                        parent = link_elem.find_element(By.XPATH, "./ancestor::article[1]")
                                    except:
                                        try:
                                            parent = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@data-zone-name, 'snippet')][1]")
                                        except:
                                            try:
                                                parent = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'snippet')][1]")
                                            except:
                                                try:
                                                    parent = link_elem.find_element(By.XPATH, "./ancestor::*[contains(@class, 'card') or contains(@class, 'item')][1]")
                                                except:
                                                    # Последняя попытка - просто родитель
                                                    parent = link_elem.find_element(By.XPATH, "./ancestor::*[position()<=5]")
                                    
                                    if parent:
                                        # Метод 1: data-auto="snippet-price-current"
                                        try:
                                            price_elems = parent.find_elements(By.CSS_SELECTOR, "[data-auto='snippet-price-current']")
                                            for price_elem in price_elems:
                                                price_text = price_elem.text
                                                price = self._extract_price(price_text)
                                                if price > 0:
                                                    break
                                        except:
                                            pass
                                        
                                        # Метод 2: Ищем в элементах с data-auto содержащим "price"
                                        if price == 0:
                                            try:
                                                price_elems = parent.find_elements(By.CSS_SELECTOR, "[data-auto*='price']")
                                                for price_elem in price_elems:
                                                    price_text = price_elem.text
                                                    p = self._extract_price(price_text)
                                                    if p > 0:
                                                        # Проверяем, не старая ли это цена
                                                        data_auto = price_elem.get_attribute('data-auto') or ''
                                                        if 'old' not in data_auto.lower():
                                                            price = p
                                                            break
                                            except:
                                                pass
                                        
                                        # Метод 3: Ищем любой элемент с ₽
                                        if price == 0:
                                            try:
                                                price_elems = parent.find_elements(By.XPATH, ".//*[contains(text(), '₽')]")
                                                # Сортируем по длине текста - берем самый короткий (обычно это цена)
                                                price_candidates = []
                                                for price_elem in price_elems:
                                                    price_text = price_elem.text.strip()
                                                    if '₽' in price_text and re.search(r'\d', price_text):
                                                        p = self._extract_price(price_text)
                                                        if p > 0:
                                                            price_candidates.append((p, len(price_text)))
                                                
                                                if price_candidates:
                                                    # Берем минимальную цену (самую короткую строку)
                                                    price_candidates.sort(key=lambda x: x[1])
                                                    price = price_candidates[0][0]
                                            except:
                                                pass
                                        
                                        # Метод 4: Ищем по классам с price/cost/value
                                        if price == 0:
                                            try:
                                                price_elems = parent.find_elements(By.CSS_SELECTOR, "*[class*='price'], *[class*='cost'], *[class*='value']")
                                                for price_elem in price_elems:
                                                    price_text = price_elem.text
                                                    if '₽' in price_text:
                                                        price = self._extract_price(price_text)
                                                        if price > 0:
                                                            break
                                            except:
                                                pass
                                except Exception as e:
                                    self.logger.debug(f"Ошибка извлечения цены через Selenium: {e}")
                                
                                # Если цена не найдена, пробуем через BeautifulSoup
                                if price == 0:
                                    try:
                                        # Пробуем найти родительский элемент разными способами
                                        parent = None
                                        try:
                                            parent = link_elem.find_element(By.XPATH, "./ancestor::article[1]")
                                        except:
                                            try:
                                                parent = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@data-zone-name, 'snippet')][1]")
                                            except:
                                                try:
                                                    parent = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'snippet')][1]")
                                                except:
                                                    parent = link_elem.find_element(By.XPATH, "./ancestor::*[contains(@class, 'card') or contains(@class, 'item')][1]")
                                        
                                        if parent:
                                            card_html = parent.get_attribute('outerHTML')
                                            soup_card = BeautifulSoup(card_html, 'html.parser')
                                            product = self._parse_product_card(soup_card, href=href)
                                            # ВАЖНО: Проверяем лимит ПЕРЕД добавлением товара
                                            if product and product.price > 0 and len(products) < max_products:
                                                products.append(product)
                                                if len(products) >= max_products:
                                                    break
                                    except Exception as e:
                                        pass
                                
                                # Парсим рейтинг и отзывы
                                rating = 0.0
                                reviews_count = 0
                                try:
                                    # Ищем родительский элемент карточки
                                    parent = None
                                    try:
                                        parent = link_elem.find_element(By.XPATH, "./ancestor::article[1]")
                                    except:
                                        try:
                                            parent = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@data-zone-name, 'snippet')][1]")
                                        except:
                                            try:
                                                parent = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'snippet')][1]")
                                            except:
                                                parent = link_elem.find_element(By.XPATH, "./ancestor::*[contains(@class, 'card') or contains(@class, 'item')][1]")
                                    
                                    if parent:
                                        # Рейтинг: ищем внутри div[data-zone-name="rating"] span с классом ds-rating__value
                                        try:
                                            # Метод 1: Ищем внутри div[data-zone-name="rating"]
                                            rating_container = parent.find_elements(By.CSS_SELECTOR, "div[data-zone-name='rating']")
                                            if rating_container:
                                                rating_elems = rating_container[0].find_elements(By.CSS_SELECTOR, "span[class*='ds-rating__value']")
                                            else:
                                                rating_elems = []
                                            
                                            if not rating_elems:
                                                # Метод 2: Ищем span с классом ds-rating__value напрямую
                                                rating_elems = parent.find_elements(By.CSS_SELECTOR, "span[class*='ds-rating__value']")
                                            if not rating_elems:
                                                # Метод 3: Ищем span с классом содержащим ds-rating
                                                rating_elems = parent.find_elements(By.CSS_SELECTOR, "span[class*='ds-rating']")
                                            
                                            for rating_elem in rating_elems:
                                                rating_text = rating_elem.text.strip()
                                                rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                                                if rating_match:
                                                    rating = float(rating_match.group(1))
                                                    # Если рейтинг больше 5.0, считаем его невалидным (0)
                                                    if rating > 5.0:
                                                        rating = 0.0
                                                    break
                                        except:
                                            pass
                                        
                                        # Отзывы: ищем внутри div[data-zone-name="rating"]
                                        try:
                                            rating_container = parent.find_elements(By.CSS_SELECTOR, "div[data-zone-name='rating']")
                                            if rating_container:
                                                reviews_elems = rating_container[0].find_elements(By.CSS_SELECTOR, "span")
                                                for reviews_elem in reviews_elems:
                                                    reviews_text = reviews_elem.text.strip()
                                                    if ('оценок' in reviews_text.lower() or 'оценка' in reviews_text.lower() or 
                                                        (re.search(r'\((\d+)\)', reviews_text) and ('купили' in reviews_text.lower() or 'оценок' in reviews_text.lower()))):
                                                        # Извлекаем число из скобок, если есть
                                                        bracket_match = re.search(r'\((\d+)\)', reviews_text)
                                                        if bracket_match:
                                                            reviews_count = int(bracket_match.group(1))
                                                        else:
                                                            reviews_match = re.search(r'(\d+)', reviews_text.replace(' ', '').replace('\xa0', ''))
                                                            if reviews_match:
                                                                reviews_count = int(reviews_match.group(1))
                                                        if reviews_count > 0:
                                                            break
                                        except:
                                            pass
                                except Exception as e:
                                    pass
                                
                                # Если нашли название и цену, создаем продукт
                                # ВАЖНО: Проверяем лимит ПЕРЕД добавлением товара
                                if title and len(title) > 5 and price > 0 and len(products) < max_products:
                                    products.append(Product(
                                        title=title[:200],
                                        price=price,
                                        url=href,
                                        source="Яндекс Маркет",
                                        availability="in_stock",
                                        rating=rating,
                                        reviews_count=reviews_count
                                    ))
                                    # Проверяем лимит после добавления
                                    if len(products) >= max_products:
                                        break
                                    
                            except Exception as e:
                                # Пробуем через BeautifulSoup как fallback только если не достигнут лимит
                                if len(products) >= max_products:
                                    continue
                                
                                # Пробуем через BeautifulSoup как fallback
                                try:
                                    # Пробуем найти родительский элемент разными способами
                                    parent = None
                                    try:
                                        parent = link_elem.find_element(By.XPATH, "./ancestor::article[1]")
                                    except:
                                        try:
                                            parent = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@data-zone-name, 'snippet')][1]")
                                        except:
                                            try:
                                                parent = link_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'snippet')][1]")
                                            except:
                                                try:
                                                    parent = link_elem.find_element(By.XPATH, "./ancestor::*[contains(@class, 'card') or contains(@class, 'item')][1]")
                                                except:
                                                    # Последняя попытка
                                                    parent = link_elem.find_element(By.XPATH, "./ancestor::*[position()<=5]")
                                    
                                    if parent:
                                        card_html = parent.get_attribute('outerHTML')
                                        soup_card = BeautifulSoup(card_html, 'html.parser')
                                        product = self._parse_product_card(soup_card, href=href)
                                        # ВАЖНО: Проверяем лимит ПЕРЕД добавлением товара
                                        if product and len(products) < max_products:
                                            products.append(product)
                                            if len(products) >= max_products:
                                                break
                                except Exception as e2:
                                    pass
                                
                                # Проверяем лимит после fallback
                                if len(products) >= max_products:
                                    break
                        except Exception as e:
                            continue
                
            except Exception as e:
                pass
            
            # Если через Selenium ничего не нашли или не набрали нужное количество, используем BeautifulSoup (старый метод)
            if len(products) < max_products:
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Яндекс Маркет использует data-zone-name для элементов
                cards = []
                
                # Метод 1: data-zone-name='snippet-card'
                cards.extend(soup.find_all(attrs={'data-zone-name': 'snippet-card'}))
                cards.extend(soup.find_all(attrs={'data-zone-name': 'productSnippet'}))
                
                # Метод 2: article с data-auto
                if not cards:
                    cards.extend(soup.find_all('article', attrs={'data-auto': True}))
                
                # Метод 3: div с data-zone-name содержащим snippet
                if not cards:
                    cards.extend(soup.find_all('div', attrs={'data-zone-name': lambda x: x and 'snippet' in str(x).lower()}))
                
                # Метод 4: элементы с data-auto содержащим snippet
                if not cards:
                    cards.extend(soup.find_all(attrs={'data-auto': lambda x: x and 'snippet' in str(x).lower()}))
                
                # Метод 5: Ищем по ссылкам на товары и строим карточки
                if not cards:
                    links = soup.find_all('a', href=lambda x: x and (('/product/' in str(x)) or ('/card/' in str(x))))
                    
                    seen_urls = set()
                    # Ограничиваем количество ссылок (как в основном цикле)
                    max_links_to_process = min(len(links), (max_products - len(products)) * 2)
                    for link in links[:max_links_to_process]:
                        # Проверяем лимит перед обработкой
                        if len(products) >= max_products:
                            break
                        
                        try:
                            # Ищем родительский элемент карточки
                            parent = link.parent
                            for _ in range(8):  # Увеличили глубину поиска
                                if parent and parent.parent and parent.name != 'body' and parent.name != 'html':
                                    parent = parent.parent
                                else:
                                    break
                            
                            if parent and parent not in cards:
                                href = link.get('href', '')
                                if href and href not in seen_urls:
                                    # Проверяем, что это действительно карточка товара
                                    # (содержит ссылку на товар и возможно цену)
                                    card_text = parent.get_text()
                                    if (('/product/' in href) or ('/card/' in href)) and (len(card_text) > 50 or '₽' in card_text or '₽' in link.get_text()):
                                        cards.append(parent)
                                        seen_urls.add(href)
                                        # Ограничиваем количество карточек с учетом уже найденных товаров
                                        if len(cards) >= (max_products - len(products)):
                                            break
                        except Exception as e:
                            continue
                
                # Убираем дубликаты
                unique_cards = []
                seen_card_ids = set()
                for card in cards:
                    try:
                        card_id = id(card)
                        if card_id not in seen_card_ids:
                            seen_card_ids.add(card_id)
                            unique_cards.append(card)
                    except:
                        continue
                
                cards = unique_cards
                
                self.logger.info(f"📦 Найдено карточек: {len(cards)}")
                
                # Обрабатываем карточки до достижения лимита
                for card in cards:
                    # Проверяем лимит перед обработкой каждой карточки
                    if len(products) >= max_products:
                        break
                    
                    try:
                        product = self._parse_product_card(card)
                        # ВАЖНО: Проверяем лимит ПЕРЕД добавлением товара
                        if product and len(products) < max_products:
                            products.append(product)
                            if len(products) >= max_products:
                                break
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
        Парсит карточку товара Яндекс Маркет
        
        Структура:
        - Ссылка содержит /product/… или /card/… (партнёрские карточки)
        - data-auto="snippet-title" - название
        - data-auto="snippet-price-current" - цена
        """
        try:
            # Ссылка
            if href:
                product_url = href.split('?')[0] if '?' in href else href
                if not product_url.startswith('http'):
                    product_url = f"https://market.yandex.ru{product_url}"
            else:
                link = card.find('a', href=lambda x: x and (('/product/' in str(x)) or ('/card/' in str(x))))
                if not link:
                    return None
                
                href = link.get('href', '')
                if not href.startswith('http'):
                    href = f"https://market.yandex.ru{href}"
                
                product_url = href.split('?')[0]
            
            # Название - пробуем несколько методов
            title = ""
            
            # Метод 1: data-auto="snippet-title" (самый надежный для Яндекс Маркет)
            title_elem = card.find(attrs={'data-auto': 'snippet-title'})
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # Метод 2: Из ссылки
            if not title or len(title) < 5:
                link_elem = card.find('a', href=lambda x: x and (('/product/' in str(x)) or ('/card/' in str(x))))
                if link_elem:
                    title = link_elem.get('title', '') or link_elem.get_text(strip=True)
            
            # Метод 3: Ищем в h3, h4, span с классами title/name/snippet
            if not title or len(title) < 5:
                found = False
                for tag in ['h3', 'h4', 'span', 'div', 'a']:
                    elems = card.find_all(tag, class_=lambda x: x and any(
                        word in str(x).lower() for word in ['title', 'name', 'product', 'snippet']
                    ))
                    for elem in elems:
                        elem_text = elem.get_text(strip=True)
                        if len(elem_text) > 10 and len(elem_text) < 200:
                            title = elem_text
                            found = True
                            break
                    if found:
                        break
            
            # Метод 4: Ищем в элементах с data-auto содержащим "title"
            if not title or len(title) < 5:
                title_elems = card.find_all(attrs={'data-auto': lambda x: x and 'title' in str(x).lower()})
                if title_elems:
                    for elem in title_elems:
                        elem_text = elem.get_text(strip=True)
                        if len(elem_text) > 10 and len(elem_text) < 200:
                            title = elem_text
                            break
            
            # Метод 5: Ищем самый длинный осмысленный текст
            if not title or len(title) < 5:
                all_texts = card.find_all(string=True, recursive=True)
                longest_text = ""
                for text in all_texts:
                    text_clean = text.strip()
                    if (len(text_clean) > 15 and 
                        len(text_clean) < 200 and
                        '₽' not in text_clean and
                        not re.match(r'^\d+$', text_clean) and
                        not re.match(r'^\d+\.\d+$', text_clean) and
                        re.search(r'[а-яёА-ЯЁa-zA-Z]', text_clean)):
                        if len(text_clean) > len(longest_text):
                            longest_text = text_clean
                
                if longest_text:
                    title = longest_text
            
            if not title or len(title) < 5:
                return None
            
            # Цена - пробуем несколько методов
            price = 0.0
            old_price = None
            
            # Метод 1: data-auto="snippet-price-current" (самый надежный для Яндекс Маркет)
            price_elem = card.find(attrs={'data-auto': 'snippet-price-current'})
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._extract_price(price_text)
            
            # Метод 2: Ищем в элементах с data-auto содержащим "price"
            if price == 0:
                price_elems = card.find_all(attrs={'data-auto': lambda x: x and 'price' in str(x).lower()})
                for price_elem in price_elems:
                    price_text = price_elem.get_text(strip=True)
                    p = self._extract_price(price_text)
                    data_auto = price_elem.get('data-auto', '')
                    if p > 0:
                        # Если это старая цена, сохраняем отдельно
                        if 'old' in str(data_auto).lower():
                            old_price = p
                        else:
                            price = p
                            break
            
            # Метод 3: Ищем любой текст с ₽
            if price == 0:
                price_elems = card.find_all(string=lambda x: x and '₽' in str(x))
                for price_elem in price_elems:
                    price_text = price_elem if isinstance(price_elem, str) else price_elem
                    p = self._extract_price(price_text)
                    if p > 0:
                        if price == 0:
                            price = p
                        elif p < price:
                            old_price = price
                            price = p
                        elif p > price:
                            old_price = p
                        break
            
            # Метод 4: Ищем в элементах с классами price/cost/value
            if price == 0:
                price_elems = card.find_all(class_=lambda x: x and any(
                    word in str(x).lower() for word in ['price', 'cost', 'value']
                ))
                for price_elem in price_elems:
                    price_text = price_elem.get_text(strip=True)
                    if '₽' in price_text:
                        p = self._extract_price(price_text)
                        if p > 0:
                            price = p
                            break
            
            # Метод 5: Ищем в span/div элементах, содержащих числа и ₽
            if price == 0:
                for tag in ['span', 'div', 'p']:
                    elems = card.find_all(tag)
                    for elem in elems:
                        elem_text = elem.get_text(strip=True)
                        if '₽' in elem_text and re.search(r'\d', elem_text):
                            p = self._extract_price(elem_text)
                            if p > 0:
                                price = p
                                break
                    if price > 0:
                        break
            
            # Старая цена
            old_price_elem = card.find(attrs={'data-auto': 'snippet-price-old'})
            if old_price_elem:
                old_price_text = old_price_elem.get_text(strip=True)
                old_price = self._extract_price(old_price_text)
            
            # Рейтинг продавца
            rating = 0.0
            # Метод 1: Ищем внутри div[data-zone-name="rating"] span с классом ds-rating__value (самый надежный)
            rating_container = card.find('div', attrs={'data-zone-name': 'rating'})
            if rating_container:
                rating_elem = rating_container.find('span', class_=lambda x: x and 'ds-rating__value' in ' '.join(x) if isinstance(x, list) else 'ds-rating__value' in str(x))
            else:
                rating_elem = None
            
            if not rating_elem:
                # Метод 2: Ищем span с классом ds-rating__value напрямую
                rating_elem = card.find('span', class_=lambda x: x and 'ds-rating__value' in ' '.join(x) if isinstance(x, list) else 'ds-rating__value' in str(x))
            if not rating_elem:
                # Метод 3: Ищем span с классом содержащим ds-rating
                rating_elem = card.find('span', class_=lambda x: x and 'ds-rating' in str(x))
            if not rating_elem:
                # Метод 4: Ищем в скрытом span для accessibility
                rating_elems = card.find_all('span', class_='ds-visuallyHidden')
                for elem in rating_elems:
                    elem_text = elem.get_text(strip=True)
                    if 'Рейтинг товара' in elem_text:
                        rating_elem = elem
                        break
            if not rating_elem:
                # Метод 5: Старый метод через data-auto
                rating_elem = card.find(attrs={'data-auto': 'rating-badge'})
            
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                try:
                    # Извлекаем число из текста типа "5.0" или "Рейтинг товара: 5.0 из 5"
                    rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                    if rating_match:
                        rating = float(rating_match.group(1))
                        # Если рейтинг больше 5.0, считаем его невалидным (0)
                        if rating > 5.0:
                            rating = 0.0
                except:
                    pass
            
            # Количество отзывов/оценок
            reviews_count = 0
            rating_container = card.find('div', attrs={'data-zone-name': 'rating'})
            if rating_container:
                reviews_elems = rating_container.find_all('span')
                for elem in reviews_elems:
                    elem_text = elem.get_text(strip=True)
                    if ('оценок' in elem_text.lower() or 'оценка' in elem_text.lower() or 
                        (re.search(r'\((\d+)\)', elem_text) and ('купили' in elem_text.lower() or 'оценок' in elem_text.lower()))):
                        # Извлекаем число из скобок, если есть
                        bracket_match = re.search(r'\((\d+)\)', elem_text)
                        if bracket_match:
                            reviews_count = int(bracket_match.group(1))
                        else:
                            reviews_match = re.search(r'(\d+)', elem_text.replace(' ', '').replace('\xa0', ''))
                            if reviews_match:
                                reviews_count = int(reviews_match.group(1))
                        if reviews_count > 0:
                            break
            
            # Изображение
            image_url = ""
            try:
                # Пробуем найти изображение разными способами
                img = card.find('img')
                if img:
                    # Пробуем разные атрибуты для изображения
                    for attr in ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-lazy', 'srcset']:
                        img_url = img.get(attr, '')
                        if img_url:
                            # Обрабатываем srcset (может содержать несколько URL)
                            if attr == 'srcset':
                                # Берем первый URL из srcset
                                img_url = img_url.split(',')[0].strip().split()[0]
                            if img_url and img_url.startswith(('http://', 'https://', '//')):
                                image_url = img_url
                                if not image_url.startswith('http'):
                                    image_url = 'https:' + image_url
                                break
                            elif img_url and img_url.startswith('/'):
                                image_url = f"https://market.yandex.ru{img_url}"
                                break
                
                # Если не нашли через img, ищем в других местах
                if not image_url:
                    # Ищем в data-атрибутах родительского элемента
                    for attr in ['data-image', 'data-img', 'data-picture']:
                        img_url = card.get(attr, '')
                        if img_url:
                            image_url = img_url
                            break
            except Exception as e:
                pass
            
            if price > 0:
                return Product(
                    title=title[:200],
                    price=price,
                    old_price=old_price,
                    url=product_url,
                    source="Яндекс Маркет",
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
    print("  ТЕСТ ЯНДЕКС МАРКЕТ SCRAPER")
    print("=" * 80)
    print()
    
    with YandexMarketScraper(headless=False) as scraper:
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
                        print(f"   ⭐ Рейтинг: {product.rating} ({product.reviews_count} отзывов)")
                    print(f"   🔗 {product.url}\n")
            else:
                print("\n⚠️ Товары не найдены")
            
            time.sleep(2)
    
    print("=" * 80)
    print("  ✅ Тестирование завершено")
    print("=" * 80)
