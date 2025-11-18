"""
Модуль для экспорта данных в Google Таблицы
"""
import logging
import socket
import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class GoogleSheetsExporter:
    """
    Класс для экспорта данных в Google Таблицы
    """
    
    def __init__(self, credentials_path: str = 'credentials.json'):
        """
        Инициализация экспортера
        
        Args:
            credentials_path: путь к файлу с credentials Service Account
        """
        self.credentials_path = Path(credentials_path)
        self.client = None
        self._initialize_client()
    
    def _check_internet_connection(self) -> bool:
        """Проверка подключения к интернету"""
        try:
            # Пробуем разрешить DNS для Google
            socket.gethostbyname('sheets.googleapis.com')
            return True
        except socket.gaierror:
            return False
    
    def _initialize_client(self):
        """Инициализация клиента Google Sheets API"""
        try:
            # Проверяем подключение к интернету
            if not self._check_internet_connection():
                raise ConnectionError(
                    "Нет подключения к интернету или не удается разрешить DNS для sheets.googleapis.com.\n"
                    "Проверьте:\n"
                    "1. Подключение к интернету\n"
                    "2. Настройки DNS\n"
                    "3. Брандмауэр и антивирус\n"
                    "4. Настройки прокси (если используется)"
                )
            
            if not self.credentials_path.exists():
                raise FileNotFoundError(
                    f"Файл credentials не найден: {self.credentials_path}\n"
                    "Создайте Service Account в Google Cloud Console и скачайте JSON ключ."
                )
            
            # Определяем область доступа
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Загружаем credentials
            creds = Credentials.from_service_account_file(
                str(self.credentials_path),
                scopes=scope
            )
            
            # Создаем клиент
            self.client = gspread.authorize(creds)
            logger.info("✅ Google Sheets клиент инициализирован")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Google Sheets клиента: {e}")
            raise
    
    def export_to_sheet(
        self,
        spreadsheet_id: str,
        data: List[Dict],
        sheet_name: str = 'Sheet1',
        clear_sheet: bool = True
    ) -> bool:
        """
        Экспортирует данные в Google Таблицу
        
        Args:
            spreadsheet_id: ID Google Таблицы (из URL)
            data: список словарей с данными для экспорта
            sheet_name: название листа (по умолчанию 'Sheet1')
            clear_sheet: очищать лист перед записью (по умолчанию True)
        
        Returns:
            True если успешно
        """
        try:
            if not self.client:
                raise RuntimeError("Google Sheets клиент не инициализирован")
            
            if not data:
                logger.warning("⚠️ Нет данных для экспорта")
                return False
            
            # Открываем таблицу
            logger.info(f"📊 Открываем таблицу: {spreadsheet_id}")
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            
            # Получаем или создаем лист
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
                logger.info(f"✅ Лист '{sheet_name}' найден")
            except gspread.exceptions.WorksheetNotFound:
                logger.info(f"📄 Создаем новый лист '{sheet_name}'")
                worksheet = spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=len(data) + 1,
                    cols=len(data[0]) if data else 10
                )
            
            # Очищаем лист если нужно
            if clear_sheet:
                logger.info("🧹 Очищаем лист...")
                worksheet.clear()
            
            # Получаем заголовки из первого элемента данных
            headers = list(data[0].keys())
            
            # Записываем заголовки
            logger.info(f"📝 Записываем заголовки: {headers}")
            worksheet.append_row(headers)
            
            # Форматируем данные для записи
            rows = []
            for row_data in data:
                row = []
                for header in headers:
                    value = row_data.get(header, '')
                    # Преобразуем None в пустую строку
                    if value is None:
                        value = ''
                    # Оставляем числа как есть (gspread сам преобразует)
                    row.append(value)
                rows.append(row)
            
            # Записываем данные батчами (Google Sheets API ограничение - 10000 ячеек за запрос)
            # Используем append_rows для более эффективной записи
            batch_size = 500  # Безопасный размер батча
            logger.info(f"📊 Записываем {len(rows)} строк данных...")
            
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                worksheet.append_rows(batch, value_input_option='USER_ENTERED')
                logger.info(f"   Записано строк: {min(i + batch_size, len(rows))} / {len(rows)}")
            
            # Форматируем заголовки (жирный шрифт)
            try:
                worksheet.format('1:1', {
                    'textFormat': {'bold': True},
                    'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                })
            except Exception as e:
                logger.warning(f"⚠️ Не удалось отформатировать заголовки: {e}")
            
            logger.info(f"✅ Данные успешно экспортированы в Google Таблицу")
            logger.info(f"   Ссылка: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")
            
            return True
            
        except gspread.exceptions.APIError as e:
            logger.error(f"❌ Ошибка API Google Sheets: {e}")
            raise
        except (ConnectionError, socket.gaierror) as e:
            error_msg = (
                "Ошибка подключения к Google Sheets API.\n"
                "Возможные причины:\n"
                "1. Нет подключения к интернету\n"
                "2. Проблемы с DNS (не удается разрешить sheets.googleapis.com)\n"
                "3. Брандмауэр или антивирус блокирует соединение\n"
                "4. Требуется настройка прокси-сервера\n\n"
                f"Детали ошибки: {str(e)}"
            )
            logger.error(f"❌ {error_msg}")
            raise ConnectionError(error_msg) from e
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта в Google Sheets: {e}")
            raise
    
    def get_spreadsheet_url(self, spreadsheet_id: str) -> str:
        """
        Возвращает URL таблицы
        
        Args:
            spreadsheet_id: ID таблицы
        
        Returns:
            URL таблицы
        """
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

