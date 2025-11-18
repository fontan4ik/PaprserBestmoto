
"""
Парсер CommerceML для системы конкурентного анализа
Поддерживает CommerceML 2.x и 3.x форматы
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Dict, Optional
import re
from pathlib import Path

@dataclass
class Product:
    """Класс для представления товара из 1С"""
    id: str
    name: str
    article: str = ""
    price: float = 0.0
    old_price: float = 0.0
    brand: str = ""
    size: str = ""
    category: str = ""
    stock: int = 0
    group_id: str = ""
    characteristics: Dict[str, str] = None

    def __post_init__(self):
        if self.characteristics is None:
            self.characteristics = {}

class CommerceMLParser:
    """Универсальный парсер CommerceML файлов"""

    def __init__(self):
        self.namespace = None
        self.groups = {}
        self.products = []

    def parse_file(self, file_path: str) -> List[Product]:
        """Парсинг XML файла CommerceML"""
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Определяем namespace
        self.namespace = self._extract_namespace(root)

        # Сначала парсим группы
        self._parse_groups(root)

        # Затем парсим товары
        self._parse_products(root)

        return self.products

    def _extract_namespace(self, root) -> Optional[str]:
        """Извлечение namespace из XML"""
        tag = root.tag
        if '}' in tag:
            return tag.split('}')[0] + '}'
        return None

    def _make_tag(self, tag_name: str) -> str:
        """Создание тега с учетом namespace"""
        if self.namespace:
            return f"{self.namespace}{tag_name}"
        return tag_name

    def _parse_groups(self, root):
        """Парсинг групп товаров"""
        classifier = root.find(self._make_tag('Классификатор'))
        if classifier is not None:
            groups_elem = classifier.find(self._make_tag('Группы'))
            if groups_elem is not None:
                self._parse_group_recursive(groups_elem, "")

    def _parse_group_recursive(self, groups_elem, parent_name: str):
        """Рекурсивный парсинг групп"""
        for group in groups_elem.findall(self._make_tag('Группа')):
            group_id = self._get_text(group, 'Ид')
            group_name = self._get_text(group, 'Наименование')

            full_name = f"{parent_name}/{group_name}" if parent_name else group_name
            self.groups[group_id] = full_name

            # Рекурсивно парсим подгруппы
            sub_groups = group.find(self._make_tag('Группы'))
            if sub_groups is not None:
                self._parse_group_recursive(sub_groups, full_name)

    def _parse_products(self, root):
        """Парсинг товаров"""
        catalog = root.find(self._make_tag('Каталог'))
        if catalog is not None:
            products_elem = catalog.find(self._make_tag('Товары'))
            if products_elem is not None:
                for product_elem in products_elem.findall(self._make_tag('Товар')):
                    product = self._parse_single_product(product_elem)
                    if product:
                        self.products.append(product)

    def _parse_single_product(self, product_elem) -> Optional[Product]:
        """Парсинг одного товара"""
        product_id = self._get_text(product_elem, 'Ид')
        name = self._get_text(product_elem, 'Наименование')

        if not product_id or not name:
            return None

        product = Product(
            id=product_id,
            name=name,
            article=self._get_text(product_elem, 'Артикул', ''),
        )

        # Парсим группу
        groups_elem = product_elem.find(self._make_tag('Группы'))
        if groups_elem is not None:
            group_id_elem = groups_elem.find(self._make_tag('Ид'))
            if group_id_elem is not None:
                product.group_id = group_id_elem.text or ""
                product.category = self.groups.get(product.group_id, "")

        # Парсим цены
        self._parse_prices(product_elem, product)

        # Парсим характеристики
        self._parse_characteristics(product_elem, product)

        # Парсим остатки
        self._parse_stock(product_elem, product)

        # Извлекаем бренд и размер из характеристик или названия
        self._extract_brand_and_size(product)

        return product

    def _parse_prices(self, product_elem, product: Product):
        """Парсинг цен товара"""
        prices_elem = product_elem.find(self._make_tag('Цены'))
        if prices_elem is not None:
            for price_elem in prices_elem.findall(self._make_tag('Цена')):
                price_value = self._get_text(price_elem, 'ЦенаЗаЕдиницу')
                if price_value:
                    try:
                        product.price = float(price_value)
                        break  # Берем первую найденную цену
                    except ValueError:
                        continue

    def _parse_characteristics(self, product_elem, product: Product):
        """Парсинг характеристик товара"""
        chars_elem = product_elem.find(self._make_tag('Характеристики'))
        if chars_elem is not None:
            for char_elem in chars_elem.findall(self._make_tag('Характеристика')):
                char_name = self._get_text(char_elem, 'Наименование')
                char_value = self._get_text(char_elem, 'Значение')
                if char_name and char_value:
                    product.characteristics[char_name] = char_value

    def _parse_stock(self, product_elem, product: Product):
        """Парсинг остатков товара"""
        stock_elem = product_elem.find(self._make_tag('Остатки'))
        if stock_elem is not None:
            stock_item = stock_elem.find(self._make_tag('Остаток'))
            if stock_item is not None:
                quantity = self._get_text(stock_item, 'Количество')
                if quantity:
                    try:
                        product.stock = int(float(quantity))
                    except ValueError:
                        product.stock = 0

    def _extract_brand_and_size(self, product: Product):
        """Извлечение бренда и размера из характеристик или названия"""
        # Из характеристик
        product.brand = product.characteristics.get('Бренд', '')
        product.size = product.characteristics.get('Размер', '')

        # Если не найдено в характеристиках, пытаемся извлечь из названия
        if not product.brand:
            # Поиск известных брендов в названии
            brands = ['HJC', 'AGV', 'SHOEI', 'ARAI', 'BELL', 'LS2']
            for brand in brands:
                if brand.upper() in product.name.upper():
                    product.brand = brand
                    break

        if not product.size:
            # Поиск размеров в названии (XS, S, M, L, XL, XXL)
            size_match = re.search(r'\b(XXL|XL|XS|[SML])\b', product.name.upper())
            if size_match:
                product.size = size_match.group(1)

    def _get_text(self, parent, tag_name: str, default: str = None) -> str:
        """Безопасное получение текста элемента"""
        elem = parent.find(self._make_tag(tag_name))
        if elem is not None and elem.text:
            return elem.text.strip()
        return default or ""

    def to_dict(self) -> Dict:
        """Конвертация результатов в словарь для JSON"""
        return {
            'groups': self.groups,
            'products': [
                {
                    'id': p.id,
                    'name': p.name,
                    'article': p.article,
                    'price': p.price,
                    'brand': p.brand,
                    'size': p.size,
                    'category': p.category,
                    'stock': p.stock,
                    'characteristics': p.characteristics
                }
                for p in self.products
            ]
        }

# Пример использования
if __name__ == "__main__":
    parser = CommerceMLParser()
    products = parser.parse_file("sample_commerceml.xml")

    print(f"Найдено товаров: {len(products)}")
    for product in products[:5]:  # Показываем первые 5
        print(f"- {product.name} ({product.price} руб.)")
