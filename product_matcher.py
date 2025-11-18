
"""
Алгоритм сопоставления товаров с использованием fuzzy matching
Поддерживает различные алгоритмы сравнения и настраиваемые веса
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import re
from difflib import SequenceMatcher
import json
import logging

# Попытка импорта дополнительных библиотек
try:
    from fuzzywuzzy import fuzz, process
    FUZZYWUZZY_AVAILABLE = True
except ImportError:
    FUZZYWUZZY_AVAILABLE = False
    print("Библиотека fuzzywuzzy не установлена. Используется базовый алгоритм.")

@dataclass
class MatchResult:
    """Результат сопоставления товаров"""
    product_1c_id: str
    product_1c_name: str
    scraped_product_title: str
    marketplace: str
    similarity_score: float
    price_1c: float
    price_scraped: float
    price_difference: float
    price_difference_percent: float
    confidence: str  # "high", "medium", "low"
    match_details: Dict[str, float]  # Детали совпадения по параметрам
    url: str = ""  # URL товара на маркетплейсе
    reviews_count: int = 0  # Количество отзывов продавца
    rating: float = 0.0  # Рейтинг продавца

    def to_dict(self):
        return {
            'product_1c_id': self.product_1c_id,
            'product_1c_name': self.product_1c_name,
            'scraped_product_title': self.scraped_product_title,
            'marketplace': self.marketplace,
            'similarity_score': round(self.similarity_score, 2),
            'price_1c': self.price_1c,
            'price_scraped': self.price_scraped,
            'price_difference': round(self.price_difference, 2),
            'price_difference_percent': round(self.price_difference_percent, 2),
            'confidence': self.confidence,
            'match_details': {k: round(v, 2) for k, v in self.match_details.items()},
            'url': self.url,
            'reviews_count': self.reviews_count,
            'rating': round(self.rating, 1) if self.rating > 0 else 0.0
        }

class ProductMatcher:
    """Класс для сопоставления товаров из 1С с найденными в интернете"""

    def __init__(self, config_file: str = "matching_config.json"):
        self.config = self._load_config(config_file)
        self.logger = logging.getLogger(__name__)

    def _load_config(self, config_file: str) -> Dict:
        """Загрузка конфигурации алгоритма сопоставления"""
        default_config = {
            "threshold": 0.85,  # Минимальный порог схожести для автоматического совпадения
            "weights": {
                "name": 0.7,     # Вес названия товара (увеличен с 0.6)
                "brand": 0.2,    # Вес бренда
                "size": 0.1      # Вес размера (увеличен с 0.15)
            },
            "algorithms": [
                "levenshtein",
                "token_similarity", 
                "fuzzy_ratio"
            ],
            "preprocessing": {
                "normalize_case": True,
                "remove_special_chars": True,
                "normalize_spaces": True,
                "common_replacements": {
                    "мотошлем": "шлем",
                    "helmet": "шлем",
                    "размер": "",
                    "size": "",
                    "цвет": "",
                    "color": ""
                }
            },
            "confidence_levels": {
                "high": 0.9,
                "medium": 0.7,
                "low": 0.5
            }
        }

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.info(f"Файл конфигурации {config_file} не найден. Используется конфигурация по умолчанию.")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            return default_config

    def match_products(self, products_1c: List[Dict], scraped_products: List[Dict], threshold: float = None) -> List[MatchResult]:
        """Основной метод сопоставления товаров"""
        # Используем переданный порог или из конфигурации
        match_threshold = threshold if threshold is not None else self.config['threshold']
        
        self.logger.info(f"🔍 Сопоставление: порог={match_threshold}, товаров 1С={len(products_1c)}, спарсено={len(scraped_products)}")
        
        matches = []
        top_scores = []  # Для отладки - сохраняем топ-5 лучших совпадений

        for idx, product_1c in enumerate(products_1c):
            # Включаем отладку для первых 2 товаров
            debug_mode = (idx < 2)
            best_matches = self._find_best_matches(product_1c, scraped_products, debug=debug_mode)
            
            # Сортируем по убыванию схожести
            best_matches.sort(key=lambda x: x.similarity_score, reverse=True)
            
            # Сохраняем топ-3 для отладки
            for match in best_matches[:3]:
                top_scores.append({
                    'product_1c': product_1c.get('name', '')[:50],
                    'scraped': match.scraped_product_title[:50],
                    'score': match.similarity_score,
                    'marketplace': match.marketplace
                })

            for match in best_matches:
                if match.similarity_score >= match_threshold:
                    matches.append(match)
        
        # Выводим топ-5 лучших совпадений для отладки
        if top_scores:
            top_scores.sort(key=lambda x: x['score'], reverse=True)
            self.logger.info(f"📊 Топ-5 лучших совпадений (все сайты):")
            for i, item in enumerate(top_scores[:5], 1):
                self.logger.info(f"   {i}. {item['score']:.2%} | {item['marketplace']} | {item['product_1c']} ↔ {item['scraped']}")

        self.logger.info(f"✅ Найдено совпадений выше порога {match_threshold:.0%}: {len(matches)}")
        return sorted(matches, key=lambda x: x.similarity_score, reverse=True)

    def _find_best_matches(self, product_1c: Dict, scraped_products: List[Dict], debug: bool = False) -> List[MatchResult]:
        """Поиск лучших совпадений для товара из 1С"""
        matches = []
        
        # Для отладки - считаем товары по источникам
        if debug:
            sources_count = {}
            for scraped in scraped_products:
                source = scraped.get('source', scraped.get('marketplace', 'unknown'))
                sources_count[source] = sources_count.get(source, 0) + 1
            if sources_count:
                self.logger.info(f"   📊 Товары по источникам: {sources_count}")

        # Собираем ВСЕ совпадения, даже с низким score (для анализа)
        all_scores = []  # Для отладки - сохраняем все оценки
        
        for scraped in scraped_products:
            similarity = self._calculate_similarity(product_1c, scraped)
            score = similarity['total_score']
            
            # Сохраняем все оценки для отладки
            if debug:
                all_scores.append({
                    'score': score,
                    'title': scraped.get('title', '')[:60],
                    'source': scraped.get('source', scraped.get('marketplace', 'unknown'))
                })

            # Создаем match для ВСЕХ товаров (убрали фильтр по confidence_levels['low'])
            # Фильтрация по threshold будет в основном методе match_products
            price_1c = float(product_1c.get('price', 0))
            price_scraped = float(scraped.get('price', 0))
            price_diff = price_scraped - price_1c
            price_diff_percent = (price_diff / price_1c * 100) if price_1c > 0 else 0

            # Определяем уровень уверенности
            confidence = self._get_confidence_level(score)

            match = MatchResult(
                product_1c_id=product_1c.get('id', ''),
                product_1c_name=product_1c.get('name', ''),
                scraped_product_title=scraped.get('title', ''),
                marketplace=scraped.get('source', scraped.get('marketplace', '')),
                similarity_score=score,
                price_1c=price_1c,
                price_scraped=price_scraped,
                price_difference=price_diff,
                price_difference_percent=price_diff_percent,
                confidence=confidence,
                match_details=similarity['details'],
                url=scraped.get('url', ''),
                reviews_count=scraped.get('reviews_count', 0),
                rating=scraped.get('rating', 0.0)
            )
            matches.append(match)
        
        # Выводим топ-5 оценок для отладки
        if debug and all_scores:
            all_scores.sort(key=lambda x: x['score'], reverse=True)
            self.logger.info(f"   🔍 Топ-5 оценок для '{product_1c.get('name', '')[:50]}':")
            for i, item in enumerate(all_scores[:5], 1):
                self.logger.info(f"      {i}. {item['score']:.2%} | {item['source']} | {item['title']}")

        return matches

    def _calculate_similarity(self, product_1c: Dict, scraped_product: Dict) -> Dict[str, any]:
        """Вычисление общей схожести между товарами"""
        weights = self.config['weights']
        details = {}

        # Сравнение названий
        name_1c = self._preprocess_text(product_1c.get('name', ''))
        name_scraped = self._preprocess_text(scraped_product.get('title', ''))
        name_similarity = self._compare_texts(name_1c, name_scraped)
        details['name'] = name_similarity

        # Сравнение брендов
        brand_1c = self._preprocess_text(product_1c.get('brand', ''))
        brand_scraped = self._extract_brand_from_title(scraped_product.get('title', ''))
        brand_similarity = self._compare_texts(brand_1c, brand_scraped) if brand_1c and brand_scraped else 0.5
        details['brand'] = brand_similarity

        # Сравнение размеров
        size_1c = product_1c.get('size', '').upper()
        size_scraped = self._extract_size_from_title(scraped_product.get('title', ''))
        size_similarity = 1.0 if size_1c == size_scraped else (0.5 if size_1c and size_scraped else 0.7)
        details['size'] = size_similarity

        # Вычисляем взвешенную сумму (категория убрана)
        total_score = (
            name_similarity * weights['name'] +
            brand_similarity * weights['brand'] +
            size_similarity * weights['size']
        )

        return {
            'total_score': total_score,
            'details': details
        }

    def _compare_texts(self, text1: str, text2: str) -> float:
        """Сравнение двух текстов с использованием различных алгоритмов"""
        if not text1 or not text2:
            return 0.0

        scores = []

        # Алгоритм 1: SequenceMatcher (базовый)
        if "levenshtein" in self.config['algorithms']:
            seq_score = SequenceMatcher(None, text1, text2).ratio()
            scores.append(seq_score)

        # Алгоритм 2: Токенное сходство
        if "token_similarity" in self.config['algorithms']:
            token_score = self._token_similarity(text1, text2)
            scores.append(token_score)

        # Алгоритм 3: FuzzyWuzzy (если доступно)
        if "fuzzy_ratio" in self.config['algorithms'] and FUZZYWUZZY_AVAILABLE:
            fuzzy_score = fuzz.ratio(text1, text2) / 100.0
            scores.append(fuzzy_score)

            # Дополнительные алгоритмы FuzzyWuzzy
            token_sort_score = fuzz.token_sort_ratio(text1, text2) / 100.0
            token_set_score = fuzz.token_set_ratio(text1, text2) / 100.0
            scores.extend([token_sort_score, token_set_score])

        # Возвращаем максимальный или средний скор
        return max(scores) if scores else 0.0

    def _token_similarity(self, text1: str, text2: str) -> float:
        """Сравнение текстов по токенам"""
        tokens1 = set(text1.lower().split())
        tokens2 = set(text2.lower().split())

        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)

        return len(intersection) / len(union) if union else 0.0

    def _preprocess_text(self, text: str) -> str:
        """Предобработка текста для сравнения"""
        if not text:
            return ""

        result = text

        # Нормализация регистра
        if self.config['preprocessing']['normalize_case']:
            result = result.lower()

        # Удаление специальных символов
        if self.config['preprocessing']['remove_special_chars']:
            result = re.sub(r'[^\w\s\-]', ' ', result)

        # Нормализация пробелов
        if self.config['preprocessing']['normalize_spaces']:
            result = re.sub(r'\s+', ' ', result).strip()

        # Общие замены
        for old, new in self.config['preprocessing']['common_replacements'].items():
            result = result.replace(old, new)

        return result

    def _extract_brand_from_title(self, title: str) -> str:
        """Извлечение бренда из названия - ищет слова большими буквами"""
        if not title:
            return ""
        
        words = title.split()
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

    def _extract_size_from_title(self, title: str) -> str:
        """Извлечение размера из названия товара"""
        # Поиск размеров в названии (XS, S, M, L, XL, XXL)
        size_match = re.search(r'\b(XXL|XL|XS|[SML])\b', title.upper())
        return size_match.group(1) if size_match else ""

    def _get_confidence_level(self, score: float) -> str:
        """Определение уровня уверенности в совпадении"""
        levels = self.config['confidence_levels']

        if score >= levels['high']:
            return "high"
        elif score >= levels['medium']:
            return "medium"
        else:
            return "low"

    def update_threshold(self, new_threshold: float):
        """Обновление порога схожести"""
        self.config['threshold'] = max(0.0, min(1.0, new_threshold))

    def get_statistics(self, matches: List[MatchResult]) -> Dict:
        """Получение статистики по совпадениям"""
        if not matches:
            return {
                'total_matches': 0,
                'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0},
                'average_similarity': 0.0,
                'marketplaces': {}
            }

        confidence_dist = {'high': 0, 'medium': 0, 'low': 0}
        marketplace_counts = {}

        for match in matches:
            confidence_dist[match.confidence] += 1
            marketplace_counts[match.marketplace] = marketplace_counts.get(match.marketplace, 0) + 1

        avg_similarity = sum(m.similarity_score for m in matches) / len(matches)

        return {
            'total_matches': len(matches),
            'confidence_distribution': confidence_dist,
            'average_similarity': round(avg_similarity, 3),
            'marketplaces': marketplace_counts
        }

# Пример использования
if __name__ == "__main__":
    # Тестовые данные
    products_1c = [
        {
            'id': 'hjc-rpha71-xl',
            'name': 'Мотошлем HJC RPHA71 CARBON XL',
            'brand': 'HJC',
            'size': 'XL',
            'price': 63000
        }
    ]

    scraped_products = [
        {
            'title': 'HJC RPHA71 CARBON CARBON XL',
            'price': 63000,
            'marketplace': 'Mr-moto.ru'
        },
        {
            'title': 'Шлем RPHA71 MATTE BLACK HJC XL',
            'price': 41690,
            'marketplace': 'Wildberries'
        }
    ]

    matcher = ProductMatcher()
    matches = matcher.match_products(products_1c, scraped_products)

    print(f"Найдено совпадений: {len(matches)}")
    for match in matches:
        print(f"- {match.product_1c_name} -> {match.scraped_product_title}")
        print(f"  Схожесть: {match.similarity_score:.2f}, Цена: {match.price_1c} -> {match.price_scraped}")
