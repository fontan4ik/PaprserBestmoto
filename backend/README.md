# Backend (FastAPI + Celery)

## Быстрый старт (локально)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env  # заполните значения
alembic upgrade head
uvicorn app.main:app --reload
```

Worker:

```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

## Стек

- FastAPI, SQLAlchemy 2.0, asyncpg
- Celery + Redis (фоновые задачи, приоритизация)
- Supabase Storage (файлы)
- Google Sheets API (экспорт)
- WebSockets (Starlette) для live-прогресса

## Полезные команды

| Команда | Описание |
| --- | --- |
| `alembic revision --autogenerate -m "..."` | новая миграция |
| `alembic upgrade head` | применить миграции |
| `pytest` *(при наличии тестов)* | запустить тесты |

## Структура

- `app/api` – эндпоинты (`auth`, `tasks`, `files`, `export`, `admin`, `stats`, `realtime`)
- `app/services` – бизнес-логика (пользователи, задачи, storage, Google Sheets, статистика, логи)
- `app/middleware` – Telegram initData + rate limiting
- `app/workers` – Celery конфигурация, задачи, периодические процессы
- `migrations` – Alembic

## Настройка окружения

Все переменные описаны в `env.example`. Минимально нужны:

- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `INITIAL_ADMIN_TELEGRAM_ID`
- БД: `DATABASE_URL`
- Redis: `REDIS_URL`
- Google: `GOOGLE_CREDENTIALS`, `GOOGLE_SERVICE_ACCOUNT_EMAIL`
- URLs: `FRONTEND_URL`, `API_BASE_URL`, `SECRET_KEY`

## Интеграция с существующими скриптами

Файл `app/services/legacy_bridge.py` инкапсулирует вызовы:

- `parse_1c_improved.Improved1CParser`
- `commerceml_parser.CommerceMLParser`
- `product_matcher.ProductMatcher`
- `scrapers.scraper_manager.ScraperManager`

Таким образом, Celery таски могут переиспользовать имеющийся функционал без рефакторинга.

