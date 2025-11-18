"""
Парсер для файла из 1С
Работает через маркеры "#" - определяет тип поля и извлекает значение
"""

import pandas as pd
import re
import logging
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Improved1CParser:
    """Парсер для файла из 1С с маркерами #"""
    
    def __init__(self):
        self.products = []
    
    def parse(self, file_path: str) -> List[Dict]:
        """Парсит файл из 1С"""
        logger.info(f"📦 Парсинг файла: {file_path}")
        
        try:
            # Читаем файл Excel
            df = pd.read_excel(file_path, header=None)
            logger.info(f"📊 Загружено строк: {len(df)}")
            
            # Пропускаем первые 34 строки
            df = df.iloc[34:].reset_index(drop=True)
            logger.info(f"📊 Обрабатываем строк: {len(df)} (первые 34 пропущены)")
            
            products = []
            rows = df.iloc[:, 0].tolist()
            total_rows = len(rows)
            i = 0
            current_product: Dict[str, str] = {}
            expecting_name = False
            
            while i < total_rows:
                raw_cell = rows[i]
                raw_text = str(raw_cell)
                
                if isinstance(raw_cell, str) and raw_text.strip().startswith('{20,2'):
                    expecting_name = True
                    i += 1
                    continue
                
                marker_value = self._extract_marker_value(raw_cell)
                
                if not marker_value:
                    i += 1
                    continue
                
                if expecting_name or self._looks_like_name(marker_value):
                    expecting_name = False
                    if current_product and 'price' in current_product:
                        product = self._create_product(current_product)
                        if product:
                            products.append(product)
                            if len(products) <= 3:
                                logger.info(f"   ✔️ Товар #{len(products)} сохранен: {product['name'][:50]}")
                    current_product = {'name': marker_value}
                    i += 1
                    continue
                
                if not current_product:
                    i += 1
                    continue
                
                if 'price' not in current_product and self._looks_like_price(marker_value):
                    price = self._parse_price(marker_value)
                    if price:
                        current_product['price'] = price
                    i += 1
                    continue
                
                if self._looks_like_variation(marker_value):
                    current_product['variation'] = self._append_text(current_product.get('variation'), marker_value)
                    i += 1
                    continue
                
                if self._looks_like_stock_value(marker_value):
                    current_product['stock'] = self._parse_stock(marker_value)
                    i += 1
                    continue
                
                if self._looks_like_description(marker_value):
                    current_product['description'] = self._append_text(current_product.get('description'), marker_value)
                
                i += 1
            
            if current_product and 'price' in current_product:
                product = self._create_product(current_product)
                if product:
                    products.append(product)
                    logger.info(f"   ✔️ Товар #{len(products)} сохранен: {product['name'][:50]}")
            
            self.products = products
            logger.info(f"✅ Успешно распарсено товаров: {len(products)}")
            
            return products
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _create_product(self, product_data: Dict) -> Optional[Dict]:
        """Создает объект товара из собранных данных"""
        try:
            name = product_data.get('name', '')
            price = product_data.get('price', 0)
            
            if not name or price <= 0:
                if len(self.products) < 3:
                    logger.warning(f"   ⚠️ Товар отклонен: name='{name[:30] if name else 'нет'}', price={price}")
                return None
            
            # Генерируем ID на основе названия
            product_id = self._generate_product_id(name)
            
            product = {
                'id': product_id,
                'name': name,
                'price': float(price),
                'brand': self._extract_brand(name),
                'stock': product_data.get('stock', 0),
                'description': product_data.get('description', ''),
                'variation': product_data.get('variation', ''),
                'source': '1C'
            }
            
            return product
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка создания товара: {e}")
            return None
    
    def _extract_brand(self, name: str) -> str:
        """Извлекает бренд из названия - ищет слова большими буквами"""
        if not name:
            return ""
        
        words = name.split()
        brands = []
        
        for word in words:
            # Убираем знаки препинания
            clean_word = word.strip('.,;:()[]{}!?-/')
            
            # Проверяем: все буквы заглавные и длина 2+ символа
            if clean_word.isupper() and len(clean_word) >= 2:
                # Пропускаем артикулы типа "М16", "S1" (буква+цифры)
                if not any(char.isdigit() for char in clean_word):
                    brands.append(clean_word)
        
        # Возвращаем первый найденный бренд или пустую строку
        return brands[0] if brands else ""
    
    def _generate_product_id(self, name: str) -> str:
        """Создает компактный идентификатор на основе названия"""
        if not name:
            return "product"
        base = re.sub(r'[^A-Za-z0-9]+', '_', name)
        base = base.strip('_')
        return base[:50] if base else "product"
    
    def _extract_marker_value(self, cell: Optional[str]) -> Optional[str]:
        """Извлекает значение из строки вида {"#","..."}"""
        if cell is None or (isinstance(cell, float) and pd.isna(cell)):
            return None
        text = str(cell).strip()
        if not text or '{\"#' not in text:
            return None
        
        match = re.search(r'\{\"#\",\"(.*?)\"\}', text, flags=re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
    
    def _consume_next_marker(self, rows: List[str], start_idx: int) -> Tuple[int, Optional[str]]:
        """Возвращает индекс после следующего маркера и его значение"""
        j = start_idx
        total = len(rows)
        while j < total:
            value = self._extract_marker_value(rows[j])
            j += 1
            if value is None:
                continue
            return j, value
        return j, None
    
    def _looks_like_name(self, value: str) -> bool:
        """Грубая эвристика, что строка является названием товара"""
        if not value:
            return False
        lowered = value.lower()
        if any(keyword in lowered for keyword in ['цвет:', 'color:', 'размер:', 'size:']):
            return False
        if lowered.strip() in {'1#', '2#', '3#'}:
            return False
        if 'наименование' in lowered:
            return False
        if not re.search(r'[A-Za-zА-Яа-я]', value):
            return False
        stripped = value.strip()
        if '•' in stripped or '\n' in stripped:
            return False
        if len(stripped) > 120:
            return False
        cleaned = re.sub(r'[\s#]+', '', value)
        if not cleaned or cleaned.isdigit():
            return False
        return len(value.strip()) >= 3
    
    def _looks_like_variation(self, value: Optional[str]) -> bool:
        if not value:
            return False
        lowered = value.lower()
        keywords = ['цвет', 'color', 'размер', 'size', 'вариа']
        return any(key in lowered for key in keywords)
    
    def _looks_like_description(self, value: Optional[str]) -> bool:
        if not value:
            return False
        value = value.strip()
        if value in {'1#', '2#', '#'}:
            return False
        has_letters = re.search(r'[A-Za-zА-Яа-я]', value) is not None
        return has_letters and len(value) > 2
    
    def _looks_like_price(self, value: Optional[str]) -> bool:
        if not value:
            return False
        if '#' in value:
            return False
        cleaned = (value.replace('\u00a0', ' ')
                         .replace('\u202f', ' ')
                         .replace('\ufffd', ' ')
                         .lower()
                         .replace('руб', '')
                         .replace('р.', '')
                         .replace('р', '')
                         .replace('₽', '')
                         .replace('~', '')
                         .strip())
        digits_only = re.sub(r'\D', '', cleaned)
        has_separator = any(ch in value for ch in [',', '.', ' ', '\u00a0', '\u202f'])
        if len(digits_only) < 2 and not has_separator:
            return False
        if re.search(r'[A-Za-zА-Яа-я]', cleaned):
            return False
        return True
    
    def _looks_like_stock_value(self, value: Optional[str]) -> bool:
        if not value:
            return False
        cleaned = (value.strip()
                        .replace('#', '')
                        .replace('шт', '')
                        .replace('шт.', '')
                        .replace(' ', '')
                        .replace('\u00a0', '')
                        .replace('\u202f', ''))
        cleaned = cleaned.replace(' ', '')
        return bool(re.fullmatch(r'[\d,.]+', cleaned))
    
    def _parse_price(self, value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        cleaned = re.sub(r'[^\d,\.]', '', value.replace('\ufffd', ''))
        cleaned = cleaned.replace(' ', '').replace(',', '.')
        try:
            price = float(cleaned)
            return price if price > 0 else None
        except Exception:
            return None
    
    def _parse_stock(self, value: Optional[str]) -> int:
        if not value:
            return 0
        cleaned = value.replace('#', ' ')
        match = re.search(r'(\d+)', cleaned)
        if match:
            return int(match.group(1))
        return 0
    
    def _append_text(self, existing: Optional[str], addition: str) -> str:
        if not addition:
            return existing or ""
        if existing:
            return f"{existing}\n{addition}"
        return addition
    
    
    def get_products(self) -> List[Dict]:
        """Возвращает список товаров"""
        return self.products
    
    def export_to_csv(self, output_path: str = "products_1c_improved.csv"):
        """Экспортирует в CSV"""
        if not self.products:
            logger.warning("⚠️ Нет товаров для экспорта")
            return
        
        df = pd.DataFrame(self.products)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"✅ Экспортировано в: {output_path}")


# Тестирование
if __name__ == "__main__":
    print("=" * 80)
    print("  УЛУЧШЕННЫЙ ПАРСЕР 1С")
    print("=" * 80)
    print()
    
    parser = Improved1CParser()
    
    # Парсим файл
    products = parser.parse("Ostatki7noyabrya (1).mxl.xlsx")
    
    if products:
        print(f"\n✅ Найдено товаров: {len(products)}\n")
        
        # Показываем первые 30
        for i, product in enumerate(products[:30], 1):
            print(f"{i}. {product['name'][:70]}")
            print(f"   💰 Цена: {product['price']:,.2f}₽")
            if product.get('brand'):
                print(f"   🏷️ Бренд: {product['brand']}")
            print()
        
        # Статистика по брендам
        print("\n" + "=" * 80)
        print("\nТОП-10 БРЕНДОВ:")
        print("-" * 80)
        
        from collections import Counter
        brands = Counter([p['brand'] for p in products if p['brand']])
        for brand, count in brands.most_common(10):
            print(f"  {brand}: {count} товаров")
        
        # Экспортируем
        parser.export_to_csv()
        
    else:
        print("\n⚠️ Товары не найдены")
    
    print("\n" + "=" * 80)
