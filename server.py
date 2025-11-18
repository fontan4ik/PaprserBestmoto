"""
Flask сервер для веб-интерфейса системы конкурентного анализа
"""
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import os
import json
from datetime import datetime
from main_system import CompetitiveAnalysisSystem
from commerceml_parser import CommerceMLParser
import logging
from flask_socketio import SocketIO, emit

app = Flask(__name__)
CORS(app)
# Используем threading mode для Socket.IO (не требует eventlet/gevent)
# Добавляем настройки для правильного закрытия соединений
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    logger=False,
    engineio_logger=False
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальная переменная для системы
analysis_system = None

@app.route('/')
def index():
    """Главная страница"""
    try:
        if not os.path.exists('index.html'):
            logger.error("Файл index.html не найден")
            return "Ошибка: файл index.html не найден", 404
        return send_from_directory('.', 'index.html')
    except Exception as e:
        logger.error(f"Ошибка при загрузке index.html: {e}")
        return f"Ошибка сервера: {str(e)}", 500

@app.route('/<path:path>')
def serve_static(path):
    """Статические файлы"""
    try:
        if not os.path.exists(path):
            logger.warning(f"Файл не найден: {path}")
            return f"Файл не найден: {path}", 404
        return send_from_directory('.', path)
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла {path}: {e}")
        return f"Ошибка сервера: {str(e)}", 500

def emit_progress(stage, message, progress=None):
    """Отправка прогресса через WebSocket"""
    data = {'stage': stage, 'message': message}
    if progress is not None:
        data['progress'] = progress
    socketio.emit('progress_update', data)

@app.route('/api/upload-xml', methods=['POST'])
def upload_xml():
    """Загрузка и парсинг XML или Excel файла из 1С"""
    global analysis_system
    
    try:
        emit_progress('start', 'Начало загрузки файла', 0)
        
        if 'file' not in request.files:
            emit_progress('error', 'Файл не найден')
            return jsonify({'error': 'Файл не найден'}), 400
        
        file = request.files['file']
        if file.filename == '':
            emit_progress('error', 'Файл не выбран')
            return jsonify({'error': 'Файл не выбран'}), 400
        
        # Определяем расширение файла
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ['.xlsx', '.xls', '.xml']:
            emit_progress('error', 'Неподдерживаемый формат файла')
            return jsonify({'error': 'Поддерживаются только файлы Excel (.xlsx, .xls) и XML'}), 400
            
        temp_filename = f'temp_upload{file_ext}'
        temp_path = os.path.join('data', temp_filename)
        
        # Создаем директорию, если её нет
        os.makedirs('data', exist_ok=True)
        
        # Сохраняем файл
        emit_progress('upload', 'Сохранение файла...', 10)
        file.save(temp_path)
        
        # Создаем новую систему
        analysis_system = CompetitiveAnalysisSystem()
        
        # Загружаем файл в зависимости от расширения
        emit_progress('parse', 'Обработка файла...', 30)
        try:
            # Use load_catalog_from_1c for both XML and Excel files as it handles both formats
            success = analysis_system.load_catalog_from_1c(temp_path)
                
            emit_progress('process', 'Обработка данных...', 70)
            
            if not success:
                emit_progress('error', 'Ошибка при обработке файла')
                return jsonify({'error': 'Ошибка при обработке файла'}), 500
                
            # Готовим данные для ответа
            products = []
            total_products = len(analysis_system.products_1c)
            for i, p in enumerate(analysis_system.products_1c[:100]):  # Ограничиваем кол-во товаров для ответа
                products.append({
                    'id': p.get('id', ''),
                    'name': p.get('name', ''),
                    'article': p.get('article', ''),
                    'price': p.get('price', 0),
                    'stock': p.get('stock', 0),
                    'brand': p.get('brand', '')
                })
                # Обновляем прогресс
                if i % 10 == 0:  # Обновляем каждые 10 товаров
                    progress = 70 + int(30 * (i / min(100, total_products)))
                    emit_progress('process', f'Обработано {i} из {min(100, total_products)} товаров', progress)
            
            emit_progress('complete', 'Обработка завершена', 100)
            return jsonify({
                'success': True,
                'products_count': len(analysis_system.products_1c),
                'products': products
            })
            
        except Exception as e:
            logger.error(f"Ошибка при обработке файла: {e}")
            emit_progress('error', f'Ошибка: {str(e)}')
            return jsonify({'error': str(e)}), 500
            
        finally:
            # Удаляем временный файл
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.error(f"Ошибка при удалении временного файла: {e}")
    
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла: {e}")
        emit_progress('error', f'Ошибка: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-sites', methods=['GET'])
def get_sites():
    """Получение списка настроенных сайтов"""
    try:
        with open('scraper_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        sites = []
        for site_id, site_data in config.get('sites', {}).items():
            sites.append({
                'id': site_id,
                'name': site_data.get('name'),
                'active': site_data.get('active', True),
                'search_url': site_data.get('search_url'),
                'selectors': site_data.get('selectors', {})
            })
        
        return jsonify({'sites': sites})
    
    except Exception as e:
        logger.error(f"Ошибка при получении списка сайтов: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-site', methods=['POST'])
def update_site():
    """Обновление настроек сайта"""
    try:
        data = request.json
        site_id = data.get('site_id')
        active = data.get('active')
        
        with open('scraper_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if site_id in config['sites']:
            config['sites'][site_id]['active'] = active
            
            with open('scraper_config.json', 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Сайт не найден'}), 404
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении настроек сайта: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/run-analysis', methods=['POST'])
def run_analysis():
    """Запуск анализа конкурентов"""
    global analysis_system
    
    if not analysis_system or not analysis_system.products_1c:
        return jsonify({'error': 'Сначала загрузите каталог из 1С'}), 400
    
    try:
        data = request.json or {}
        threshold = data.get('threshold', 0.85)
        max_products = data.get('max_products', 5)  # Количество товаров из 1С
        selected_sites = data.get('sites', None)  # Выбранные сайты
        
        logger.info(f"Параметры анализа: порог={threshold}, товаров={max_products}, сайты={selected_sites}")
        
        # Парсинг конкурентов
        logger.info("Начало парсинга конкурентов...")
        emit_progress('scraping', f'Парсинг {max_products} товаров...', 20)
        
        try:
            stats = analysis_system.scrape_competitors(
                sites=selected_sites,
                max_products_from_1c=max_products
            )
            logger.info(f"Парсинг завершен: {stats}")
            emit_progress('matching', 'Сопоставление товаров...', 60)
        except Exception as e:
            logger.error(f"Ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
            emit_progress('error', f'Ошибка парсинга: {str(e)}')
            return jsonify({'error': f'Ошибка при парсинге конкурентов: {str(e)}'}), 500
        
        # Сопоставление товаров
        logger.info("Сопоставление товаров...")
        try:
            success = analysis_system.match_products(threshold=threshold)
            if not success:
                logger.warning("Сопоставление не удалось")
            emit_progress('reporting', 'Генерация отчета...', 80)
        except Exception as e:
            logger.error(f"Ошибка при сопоставлении: {e}")
            import traceback
            traceback.print_exc()
            emit_progress('error', f'Ошибка сопоставления: {str(e)}')
            return jsonify({'error': f'Ошибка при сопоставлении товаров: {str(e)}'}), 500
        
        # Генерация отчета
        logger.info("Генерация отчета...")
        try:
            report_path = analysis_system.generate_report('json')
            
            if not report_path:
                logger.error("Не удалось создать отчет")
                emit_progress('error', 'Не удалось создать отчет')
                return jsonify({'error': 'Не удалось создать отчет'}), 500
            
            # Читаем отчет
            with open(report_path, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
            
            emit_progress('complete', 'Анализ завершен', 100)
            
            return jsonify({
                'success': True,
                'report': report_data,
                'report_path': report_path
            })
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {e}")
            import traceback
            traceback.print_exc()
            emit_progress('error', f'Ошибка генерации отчета: {str(e)}')
            return jsonify({'error': f'Ошибка при генерации отчета: {str(e)}'}), 500
    
    except Exception as e:
        logger.error(f"Критическая ошибка при выполнении анализа: {e}")
        import traceback
        traceback.print_exc()
        emit_progress('error', f'Критическая ошибка: {str(e)}')
        return jsonify({'error': f'Критическая ошибка: {str(e)}'}), 500

@app.route('/api/export-report', methods=['POST'])
def export_report():
    """Экспорт отчета в различных форматах"""
    global analysis_system
    
    if not analysis_system:
        return jsonify({'error': 'Нет данных для экспорта'}), 400
    
    try:
        data = request.json
        format_type = data.get('format', 'excel')
        
        report_path = analysis_system.generate_report(format_type)
        
        if not report_path:
            return jsonify({'error': 'Не удалось создать отчет'}), 500
        
        return jsonify({
            'success': True,
            'report_path': str(report_path),
            'message': f'Отчет сохранен: {report_path}'
        })
    
    except Exception as e:
        logger.error(f"Ошибка при экспорте отчета: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-report', methods=['GET'])
def download_report():
    """Скачивание файла отчета"""
    try:
        report_path = request.args.get('path')
        if not report_path:
            return jsonify({'error': 'Не указан путь к файлу'}), 400
        
        from pathlib import Path
        file_path = Path(report_path)
        
        if not file_path.exists():
            return jsonify({'error': 'Файл не найден'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_path.name,
            mimetype='text/csv' if file_path.suffix == '.csv' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    except Exception as e:
        logger.error(f"Ошибка при скачивании отчета: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-google-sheets', methods=['POST'])
def export_google_sheets():
    """Экспорт отчета в Google Таблицу"""
    global analysis_system
    
    if not analysis_system:
        return jsonify({'error': 'Нет данных для экспорта'}), 400
    
    try:
        data = request.json
        spreadsheet_id = data.get('spreadsheet_id')
        
        if not spreadsheet_id:
            return jsonify({'error': 'Не указан ID таблицы'}), 400
        
        # Опциональные параметры
        credentials_path = data.get('credentials_path', 'credentials.json')
        sheet_name = data.get('sheet_name', 'Sheet1')
        
        logger.info(f"Экспорт в Google Таблицу: {spreadsheet_id}")
        
        # Выполняем экспорт
        success = analysis_system.export_to_google_sheets(
            spreadsheet_id=spreadsheet_id,
            credentials_path=credentials_path,
            sheet_name=sheet_name
        )
        
        if success:
            from google_sheets_exporter import GoogleSheetsExporter
            exporter = GoogleSheetsExporter(credentials_path=credentials_path)
            spreadsheet_url = exporter.get_spreadsheet_url(spreadsheet_id)
            
            return jsonify({
                'success': True,
                'spreadsheet_id': spreadsheet_id,
                'spreadsheet_url': spreadsheet_url,
                'message': 'Данные успешно экспортированы в Google Таблицу'
            })
        else:
            return jsonify({'error': 'Не удалось экспортировать данные'}), 500
    
    except FileNotFoundError as e:
        logger.error(f"Файл credentials не найден: {e}")
        return jsonify({
            'error': f'Файл credentials не найден: {credentials_path}\n'
                    'Создайте Service Account в Google Cloud Console и скачайте JSON ключ.'
        }), 400
    except ConnectionError as e:
        logger.error(f"Ошибка подключения: {e}")
        error_message = str(e)
        return jsonify({
            'error': error_message,
            'type': 'connection_error'
        }), 503
    except Exception as e:
        logger.error(f"Ошибка при экспорте в Google Sheets: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-matching-config', methods=['GET'])
def get_matching_config():
    """Получение конфигурации сопоставления"""
    try:
        with open('matching_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        logger.error(f"Ошибка при получении конфигурации: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-matching-config', methods=['POST'])
def update_matching_config():
    """Обновление конфигурации сопоставления"""
    try:
        data = request.json
        
        with open('matching_config.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Ошибка при обновлении конфигурации: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Получение статуса системы"""
    global analysis_system
    
    if not analysis_system:
        return jsonify({
            'initialized': False,
            'products_loaded': 0,
            'scraped_products': 0,
            'matches': 0
        })
    
    return jsonify({
        'initialized': True,
        'products_loaded': len(analysis_system.products_1c),
        'scraped_products': len(analysis_system.scraped_products),
        'matches': len(analysis_system.matches)
    })

def cleanup_resources():
    """Очистка ресурсов при завершении сервера"""
    global analysis_system
    try:
        if analysis_system and hasattr(analysis_system, 'scraper_manager'):
            logger.info('🧹 Закрываем браузеры...')
            analysis_system.scraper_manager.close_all()
            logger.info('✅ Браузеры закрыты')
    except Exception as e:
        logger.error(f'⚠️ Ошибка при очистке ресурсов: {e}')

if __name__ == '__main__':
    try:
        # Показываем текущую директорию
        current_dir = os.getcwd()
        print('=' * 60)
        print('🚀 Запуск веб-сервера системы конкурентного анализа')
        print('=' * 60)
        print(f'📂 Рабочая директория: {current_dir}')
        
        # Проверяем наличие необходимых файлов
        required_files = ['index.html', 'app.js', 'style.css', 'server.py']
        missing_files = []
        for file in required_files:
            if not os.path.exists(file):
                missing_files.append(file)
        
        if missing_files:
            print(f'⚠️  Отсутствуют файлы: {", ".join(missing_files)}')
            print(f'   Убедитесь, что вы запускаете сервер из правильной директории')
        else:
            print('✅ Все необходимые файлы найдены')
        
        # Создаем необходимые директории
        os.makedirs('data', exist_ok=True)
        os.makedirs('data/logs', exist_ok=True)
        os.makedirs('data/reports', exist_ok=True)
        
        print(f'📍 Адрес: http://localhost:5000')
        print('=' * 60)
        print('Нажмите Ctrl+C для остановки сервера')
        print('=' * 60)
        
        # Проверяем импорты перед запуском
        try:
            from main_system import CompetitiveAnalysisSystem
            from commerceml_parser import CommerceMLParser
            print('✅ Все модули импортированы успешно')
        except ImportError as e:
            print(f'❌ Ошибка импорта модулей: {e}')
            import traceback
            traceback.print_exc()
            exit(1)
        
        print('\n🟢 Сервер запускается...\n')
        # Используем use_reloader=False чтобы избежать проблем с перезагрузкой
        socketio.run(
            app, 
            host='0.0.0.0', 
            port=5000, 
            debug=True, 
            allow_unsafe_werkzeug=True,
            use_reloader=False  # Отключаем автоперезагрузку для стабильности
        )
    except KeyboardInterrupt:
        print('\n\n🛑 Сервер остановлен пользователем')
        cleanup_resources()
    except Exception as e:
        print(f'\n\n❌ Критическая ошибка при запуске сервера: {e}')
        import traceback
        traceback.print_exc()
        cleanup_resources()
        exit(1)
    finally:
        print('🧹 Финальная очистка...')
        cleanup_resources()
        print('✅ Сервер полностью остановлен')
