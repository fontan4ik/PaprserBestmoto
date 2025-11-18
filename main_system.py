"""
Главная система конкурентного анализа v3.0
С новыми Selenium скраперами для каждого маркетплейса
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional
import json
import csv
from datetime import datetime

from scrapers.scraper_manager import ScraperManager, ScrapedProduct
from commerceml_parser import CommerceMLParser
from product_matcher import ProductMatcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class CompetitiveAnalysisSystem:
    """
    Система конкурентного анализа v3.0
    
    Возможности:
    - Загрузка каталога из 1С (XML/Excel)
    - Парсинг 9 маркетплейсов с помощью Selenium
    - Интеллектуальное сопоставление товаров
    - Генерация детальных отчетов
    """
    
    def __init__(self, headless: bool = True):
        """
        Args:
            headless: запускать браузеры без GUI
        """
        self.headless = headless
        
        # Компоненты системы
        self.scraper_manager = ScraperManager(headless=headless)
        self.xml_parser = CommerceMLParser()
        self.matcher = ProductMatcher()
        
        # Данные
        self.products_1c = []
        self.products_1c_limited = []  # Ограниченный список для парсинга и сопоставления
        self.scraped_products = []
        self.matches = []
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("✅ Система инициализирована")
        self.logger.info(f"   Режим браузера: {'headless' if headless else 'с GUI'}")
    
    def load_catalog_from_1c(self, file_path: str) -> bool:
        """
        Загружает каталог из 1С
        
        Args:
            file_path: путь к файлу (XML или Excel)
        
        Returns:
            True если успешно
        """
        self.logger.info(f"📦 Загрузка каталога: {file_path}")
        
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext in ['.xml']:
                # XML файл
                success = self.xml_parser.parse(file_path)
                if success:
                    self.products_1c = self.xml_parser.get_products()
            
            elif file_ext in ['.xlsx', '.xls']:
                # Excel файл (файл из 1С)
                from parse_1c_improved import Improved1CParser
                parser = Improved1CParser()
                self.products_1c = parser.parse(file_path)
            
            else:
                self.logger.error(f"❌ Неподдерживаемый формат: {file_ext}")
                return False
            
            if self.products_1c:
                self.logger.info(f"✅ Загружено товаров: {len(self.products_1c)}")
                return True
            else:
                self.logger.warning("⚠️ Товары не найдены в файле")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка загрузки: {e}")
            return False
    
    def scrape_competitors(
        self,
        sites: Optional[List[str]] = None,
        max_products_per_site: int = 20,
        max_products_from_1c: int = 5
    ) -> Dict[str, int]:
        """
        Парсит конкурентов
        
        Args:
            sites: список сайтов (None = все)
            max_products_per_site: макс товаров с каждого сайта
            max_products_from_1c: количество товаров из 1С для парсинга
        
        Returns:
            статистика {сайт: количество}
        """
        if not self.products_1c:
            self.logger.warning("⚠️ Сначала загрузите каталог из 1С")
            return {}
        
        self.logger.info(f"🔍 Начало парсинга конкурентов")
        self.logger.info(f"   Товаров из 1С: {max_products_from_1c}")
        self.logger.info(f"   Сайты: {sites if sites else 'все'}")
        
        # Очищаем данные перед новым парсингом
        self.scraped_products = []
        self.matches = []
        
        stats = {}
        
        # ВАЖНО: Ограничиваем список товаров для парсинга И для сопоставления
        # Сохраняем ограниченный список для использования в match_products и generate_report
        self.products_1c_limited = self.products_1c[:max_products_from_1c]
        
        self.logger.info(f"   Обрабатываем {len(self.products_1c_limited)} товаров из 1С (всего в каталоге: {len(self.products_1c)})")
        
        for idx, product_1c in enumerate(self.products_1c_limited, 1):
            query = product_1c.get('name', '')
            
            if not query:
                continue
            
            self.logger.info(f"\n📦 [{idx}/{len(self.products_1c_limited)}] Товар: {query}")
            
            # Поиск на всех сайтах
            results = self.scraper_manager.search_all(
                query=query,
                sites=sites,
                max_products=max_products_per_site
            )
            
            # Собираем результаты
            for site, products in results.items():
                if site not in stats:
                    stats[site] = 0
                
                stats[site] += len(products)
                
                # Добавляем в общий список
                for product in products:
                    self.scraped_products.append(product.to_dict())
        
        self.logger.info(f"\n✅ Парсинг завершен")
        self.logger.info(f"   Всего найдено: {len(self.scraped_products)} товаров")
        
        return stats
    
    def match_products(self, threshold: float = 0.75) -> bool:
        """
        Сопоставляет товары из 1С с найденными
        
        Args:
            threshold: порог схожести (0-1)
        
        Returns:
            True если успешно
        """
        if not self.products_1c or not self.scraped_products:
            self.logger.warning("⚠️ Нет данных для сопоставления")
            return False
        
        self.logger.info(f"🔗 Сопоставление товаров (порог: {threshold})")
        
        # Используем ограниченный список товаров из 1С для сопоставления
        products_for_matching = self.products_1c_limited if self.products_1c_limited else self.products_1c
        
        self.matches = self.matcher.match_products(
            products_for_matching,
            self.scraped_products,
            threshold=threshold
        )
        
        self.logger.info(f"✅ Найдено совпадений: {len(self.matches)}")
        
        return True
    
    def generate_report(self, format: str = 'json') -> str:
        """
        Генерирует отчет
        
        Args:
            format: формат отчета (json, csv, excel)
        
        Returns:
            путь к файлу отчета
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_dir = Path('data/reports')
        report_dir.mkdir(parents=True, exist_ok=True)
        
        if format == 'json':
            report_path = report_dir / f'competitive_analysis_{timestamp}.json'
            
            # Convert MatchResult objects to dicts if needed
            matches_data = []
            for match in self.matches:
                if hasattr(match, 'to_dict'):
                    matches_data.append(match.to_dict())
                else:
                    matches_data.append(match)
            
            report_data = {
                'generated_at': datetime.now().isoformat(),
                'summary': {
                    'total_products_1c': len(self.products_1c),
                    'total_scraped_products': len(self.scraped_products),
                    'total_matches': len(self.matches),
                },
                'products_1c': self.products_1c,
                'scraped_products': self.scraped_products,
                'matches': matches_data,
            }
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        elif format == 'csv':
            import pandas as pd
            report_path = report_dir / f'analiz_{timestamp}.csv'
            
            # Создаем читаемый отчет
            report_data = []
            
            # Группируем совпадения по товарам из 1С
            products_with_matches = {}
            for match in self.matches:
                match_dict = match.to_dict() if hasattr(match, 'to_dict') else match
                product_id = match_dict.get('product_1c_id', '')
                
                if product_id not in products_with_matches:
                    products_with_matches[product_id] = {
                        'product': match_dict,
                        'matches': []
                    }
                products_with_matches[product_id]['matches'].append(match_dict)
            
            # Формируем строки отчета (используем только обработанные товары)
            # Используем ограниченный список товаров из 1С, если он был создан
            products_for_report = self.products_1c_limited if self.products_1c_limited else self.products_1c
            product_number = 1  # Счетчик для нумерации товаров
            
            for product_1c in products_for_report:
                product_id = product_1c.get('id', '')
                product_name = product_1c.get('name', '')
                product_price = product_1c.get('price', 0)
                
                if product_id in products_with_matches:
                    # Есть совпадения - все строки получают один номер
                    matches = products_with_matches[product_id]['matches']
                    for match in matches:
                        report_data.append({    
                            'Нумерация': product_number,
                            'Товар 1С': product_name,
                            'Артикул': product_id,
                            'Цена 1С (руб)': product_price,
                            'Маркетплейс': match.get('marketplace', ''),
                            'Название на маркетплейсе': match.get('scraped_product_title', ''),
                            'Цена конкурента (руб)': match.get('price_scraped', 0),
                            'Разница (руб)': match.get('price_difference', 0),
                            'Совпадение (%)': round(match.get('similarity_score', 0) * 100, 1),
                            'Отзывов': match.get('reviews_count', 0),
                            'Рейтинг': str(round(match.get('rating', 0.0), 1)).replace('.', ',') if match.get('rating', 0.0) > 0 else '',
                            'Ссылка': match.get('url', '')
                        })
                else:
                    # Нет совпадений - тоже получает номер
                    report_data.append({
                        'Нумерация': product_number,
                        'Товар 1С': product_name,
                        'Артикул': product_id,
                        'Цена 1С (руб)': product_price,
                        'Маркетплейс': 'Не найдено',
                        'Название на маркетплейсе': '',
                        'Цена конкурента (руб)': '',
                        'Разница (руб)': '',
                        'Совпадение (%)': '',
                        'Отзывов': '',
                        'Рейтинг': '',
                        'Ссылка': ''
                    })
                
                # Увеличиваем номер только при переходе к следующему товару
                product_number += 1
            
            if report_data:
                df = pd.DataFrame(report_data)
                # Используем точку с запятой как разделитель для корректного открытия в Excel (русская локаль)
                # encoding='utf-8-sig' добавляет BOM для правильного отображения кириллицы
                # quoting=1 (QUOTE_ALL) - все поля в кавычках для безопасности
                df.to_csv(
                    report_path, 
                    index=False, 
                    encoding='utf-8-sig', 
                    sep=';',
                    quoting=csv.QUOTE_ALL,
                    escapechar=None
                )
            else:
                self.logger.warning("⚠️ Нет данных для CSV отчета")
                return ""
        
        elif format == 'excel':
            import pandas as pd
            report_path = report_dir / f'competitive_analysis_{timestamp}.xlsx'
            
            with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
                if self.matches:
                    # Convert MatchResult objects to dicts if needed
                    matches_data = []
                    for match in self.matches:
                        if hasattr(match, 'to_dict'):
                            matches_data.append(match.to_dict())
                        else:
                            matches_data.append(match)
                    df_matches = pd.DataFrame(matches_data)
                    
                    # Добавляем нумерацию по товарам из 1С
                    # Группируем по product_1c_id и присваиваем одинаковые номера
                    if 'product_1c_id' in df_matches.columns:
                        # Получаем уникальные товары в порядке появления
                        unique_products = df_matches['product_1c_id'].drop_duplicates().reset_index(drop=True)
                        # Создаем словарь: product_id -> номер
                        product_to_number = {product_id: idx + 1 for idx, product_id in enumerate(unique_products)}
                        # Применяем нумерацию
                        df_matches['Нумерация'] = df_matches['product_1c_id'].map(product_to_number)
                        # Перемещаем столбец в начало
                        cols = ['Нумерация'] + [col for col in df_matches.columns if col != 'Нумерация']
                        df_matches = df_matches[cols]
                    else:
                        # Если нет product_1c_id, используем простую нумерацию
                        df_matches.insert(0, 'Нумерация', range(1, len(df_matches) + 1))
                    
                    # Удаляем столбец "Разница (%)" если он есть
                    if 'price_difference_percent' in df_matches.columns:
                        df_matches = df_matches.drop(columns=['price_difference_percent'])
                    
                    # Заменяем точку на запятую в рейтинге для корректного отображения в Excel
                    if 'rating' in df_matches.columns:
                        df_matches['rating'] = df_matches['rating'].apply(
                            lambda x: str(x).replace('.', ',') if x and x != 0 and pd.notna(x) else ''
                        )
                    
                    df_matches.to_excel(writer, sheet_name='Совпадения', index=False)
                
                if self.products_1c:
                    df_1c = pd.DataFrame(self.products_1c)
                    df_1c.to_excel(writer, sheet_name='Товары 1С', index=False)
                
                if self.scraped_products:
                    df_scraped = pd.DataFrame(self.scraped_products)
                    # Заменяем точку на запятую в рейтинге для корректного отображения в Excel
                    if 'rating' in df_scraped.columns:
                        df_scraped['rating'] = df_scraped['rating'].apply(
                            lambda x: str(x).replace('.', ',') if x and x != 0 and pd.notna(x) else ''
                        )
                    df_scraped.to_excel(writer, sheet_name='Спарсено', index=False)
        
        else:
            self.logger.error(f"❌ Неизвестный формат: {format}")
            return ""
        
        self.logger.info(f"✅ Отчет создан: {report_path}")
        return str(report_path)
    
    def export_to_google_sheets(
        self,
        spreadsheet_id: str,
        credentials_path: str = 'credentials.json',
        sheet_name: str = 'Sheet1'
    ) -> bool:
        """
        Экспортирует данные в Google Таблицу
        
        Args:
            spreadsheet_id: ID Google Таблицы (из URL)
            credentials_path: путь к файлу с credentials Service Account
            sheet_name: название листа (по умолчанию 'Sheet1')
        
        Returns:
            True если успешно
        """
        try:
            from google_sheets_exporter import GoogleSheetsExporter
            
            self.logger.info(f"📊 Экспорт в Google Таблицу: {spreadsheet_id}")
            
            # Инициализируем экспортер
            exporter = GoogleSheetsExporter(credentials_path=credentials_path)
            
            # Формируем данные в том же формате, что и для CSV
            report_data = []
            
            # Группируем совпадения по товарам из 1С
            products_with_matches = {}
            for match in self.matches:
                match_dict = match.to_dict() if hasattr(match, 'to_dict') else match
                product_id = match_dict.get('product_1c_id', '')
                
                if product_id not in products_with_matches:
                    products_with_matches[product_id] = {
                        'product': match_dict,
                        'matches': []
                    }
                products_with_matches[product_id]['matches'].append(match_dict)
            
            # Формируем строки отчета (используем только обработанные товары)
            products_for_report = self.products_1c_limited if self.products_1c_limited else self.products_1c
            product_number = 1
            
            for product_1c in products_for_report:
                product_id = product_1c.get('id', '')
                product_name = product_1c.get('name', '')
                product_price = product_1c.get('price', 0)
                
                if product_id in products_with_matches:
                    # Есть совпадения
                    matches = products_with_matches[product_id]['matches']
                    for match in matches:
                        report_data.append({
                            'Нумерация': product_number,
                            'Товар 1С': product_name,
                            'Артикул': product_id,
                            'Цена 1С (руб)': product_price,
                            'Маркетплейс': match.get('marketplace', ''),
                            'Название на маркетплейсе': match.get('scraped_product_title', ''),
                            'Цена конкурента (руб)': match.get('price_scraped', 0),
                            'Разница (руб)': match.get('price_difference', 0),
                            'Совпадение (%)': round(match.get('similarity_score', 0) * 100, 1),
                            'Отзывов': match.get('reviews_count', 0),
                            'Рейтинг': str(round(match.get('rating', 0.0), 1)).replace('.', ',') if match.get('rating', 0.0) > 0 else '',
                            'Ссылка': match.get('url', '')
                        })
                else:
                    # Нет совпадений
                    report_data.append({
                        'Нумерация': product_number,
                        'Товар 1С': product_name,
                        'Артикул': product_id,
                        'Цена 1С (руб)': product_price,
                        'Маркетплейс': 'Не найдено',
                        'Название на маркетплейсе': '',
                        'Цена конкурента (руб)': '',
                        'Разница (руб)': '',
                        'Совпадение (%)': '',
                        'Отзывов': '',
                        'Рейтинг': '',
                        'Ссылка': ''
                    })
                
                product_number += 1
            
            if not report_data:
                self.logger.warning("⚠️ Нет данных для экспорта в Google Sheets")
                return False
            
            # Экспортируем в Google Sheets
            success = exporter.export_to_sheet(
                spreadsheet_id=spreadsheet_id,
                data=report_data,
                sheet_name=sheet_name,
                clear_sheet=True
            )
            
            if success:
                self.logger.info(f"✅ Данные успешно экспортированы в Google Таблицу")
                self.logger.info(f"   Ссылка: {exporter.get_spreadsheet_url(spreadsheet_id)}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка экспорта в Google Sheets: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def get_status(self) -> Dict:
        """Возвращает статус системы"""
        return {
            'products_1c_loaded': len(self.products_1c),
            'scraped_products': len(self.scraped_products),
            'matches_found': len(self.matches),
            'supported_sites': list(self.scraper_manager.get_supported_sites().keys()),
        }


# Пример использования
if __name__ == "__main__":
    print("=" * 80)
    print("  СИСТЕМА КОНКУРЕНТНОГО АНАЛИЗА v3.0")
    print("=" * 80)
    print()
    
    # Создаем систему
    system = CompetitiveAnalysisSystem(headless=True)
    
    # 1. Загружаем каталог
    print("📦 Шаг 1: Загрузка каталога из 1С")
    success = system.load_catalog_from_1c("sample_commerceml.xml")
    
    if success:
        print(f"   ✅ Загружено: {len(system.products_1c)} товаров")
    
    # 2. Парсим конкурентов
    print("\n🔍 Шаг 2: Парсинг конкурентов")
    stats = system.scrape_competitors(
        sites=['wildberries', 'ozon'],  # Тестируем 2 сайта
        max_products_per_site=5
    )
    
    print("\n   Статистика:")
    for site, count in stats.items():
        print(f"     {site}: {count} товаров")
    
    # 3. Сопоставление
    print("\n🔗 Шаг 3: Сопоставление товаров")
    system.match_products(threshold=0.70)
    print(f"   ✅ Найдено совпадений: {len(system.matches)}")
    
    # 4. Генерация отчетов
    print("\n📊 Шаг 4: Генерация отчетов")
    json_report = system.generate_report('json')
    csv_report = system.generate_report('csv')
    
    print(f"   ✅ JSON: {json_report}")
    print(f"   ✅ CSV: {csv_report}")
    
    # Статус
    print("\n" + "=" * 80)
    status = system.get_status()
    print("📈 Итоговая статистика:")
    print(f"   Товаров из 1С: {status['products_1c_loaded']}")
    print(f"   Спарсено товаров: {status['scraped_products']}")
    print(f"   Найдено совпадений: {status['matches_found']}")
    print(f"   Поддерживаемые сайты: {len(status['supported_sites'])}")
    
    print("\n" + "=" * 80)
    print("  ✅ Работа завершена")
    print("=" * 80)
