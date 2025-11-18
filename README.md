# Parser BestMoto · Telegram Mini App

Полнофункциональная платформа для парсинга маркетплейсов, сопоставления данных 1С и экспорта результатов в Google Sheets. Решение строится вокруг Telegram Mini App (WebApp) с фоновой обработкой задач и административной панелью.

## Архитектура

- **Frontend** – SPA на React + Vite, использующая Telegram WebApp SDK и размещаемая на GitHub Pages / Vercel (`frontend/`).
- **Backend API** – FastAPI (Python 3.11) с PostgreSQL (Supabase), Redis (Railway/Render) и Celery worker (`backend/`).
- **Очередь и фоновые задачи** – Celery + Redis с worker и периодическими задачами (очистка Supabase Storage, архивация задач).
- **Хранилище файлов** – Supabase Storage (bucket `commerce-files`).
- **Интеграции** – Google Sheets API (service account), Telegram initData в middleware, импорт существующих скриптов (`parse_1c_improved.py`, `product_matcher.py`, `scrapers/…`).

## Backend

```
backend/
  app/
    api/            # FastAPI routers (auth, tasks, files, export, admin, stats, realtime)
    core/           # config, logging, startup events
    db/             # SQLAlchemy base + session
    middleware/     # Telegram initData + rate limiting
    models/         # Users, Tasks, Logs, Files, Mappings, Archive
    schemas/        # Pydantic DTOs
    services/       # бизнес-логика и интеграции
    workers/        # Celery app + задачи
  migrations/       # Alembic (initial revision готов)
  requirements.txt
  env.example
```

Особенности:

- Валидация Telegram initData (HMAC-SHA256) через middleware.
- Rate limiting (Redis) с разными квотами для USER / ADMIN + контроль одновременных задач.
- REST API покрывает все эндпоинты из ТЗ, включая административный функционал (пользователи, задачи, логи, статистика, экспорт).
- Celery tasks вызывают существующие скрипты через `LegacyBridge` для парсинга 1C, CommerceML и маркетплейсов.
- Redis pub/sub + WebSocket `/api/ws/tasks` для live-прогресса.
- Supabase Storage для загрузки CommerceML/XLSX; автоматическая очистка файлов старше 30 дней.
- Архивация задач старше 90 дней в отдельную таблицу `archived_tasks`.

### Локальный запуск backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env  # заполните переменные
alembic upgrade head
uvicorn app.main:app --reload
```

Запуск worker:

```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

### Переменные окружения

Смотрите `backend/env.example`. Основные блоки:

- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `INITIAL_ADMIN_TELEGRAM_ID`
- Databases: `DATABASE_URL`, `REDIS_URL`
- Google: `GOOGLE_CREDENTIALS` (base64) и `GOOGLE_SERVICE_ACCOUNT_EMAIL`
- Application: `FRONTEND_URL`, `API_BASE_URL`, `SECRET_KEY`, `ENVIRONMENT`
- Rate limits и лимиты файлов
- Supabase Storage: `SUPABASE_PROJECT_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET`

### Миграции

Alembic настроен на асинхронный движок. Команды:

```
alembic revision --autogenerate -m "..."
alembic upgrade head
```

## Frontend (Telegram Mini App)

```
frontend/
  src/
    App.tsx         # основная SPA логика (Tabs, Admin panel, Tasks, Files)
    api/client.ts   # axios с валидацией initData
    hooks/useTelegram.ts
    types.ts, styles.css
  package.json / Vite config
```

Особенности:

- Валидация initData до каждого запроса, автоматический показ Telegram MainButton / BackButton.
- Живые обновления прогресса через WebSocket.
- Тёмная/светлая тема синхронизируется с Telegram.
- Роли: вкладка «Админ» отображается только для ADMIN и включает управление пользователями, просмотр логов, статистику.
- Состояния загрузки, haptic feedback, optimistic обновления списков.

### Локальный запуск фронтенда

```bash
cd frontend
npm install
VITE_API_BASE_URL=https://localhost:8000 npm run dev
```

Для локального теста без Telegram можно задать `VITE_DEV_INIT_DATA` с sample initData (получить в BotFather или логах).

### Production build

```
npm run build
```

Папку `frontend/dist` можно деплоить на GitHub Pages (ветка `gh-pages`) или Vercel.

## Инфраструктура и деплой

Материалы в `infra/`:

- `infra/render.yaml` – пример манифеста Render с двумя сервисами (API + Celery worker) и Redis.
- `infra/README.md` – пошагово: Supabase, Render, Railway/Redis, GitHub Pages/Vercel, Telegram BotFather.

Кратко:

1. **Supabase**
   - Создать проект, скопировать `DATABASE_URL`.
   - Создать bucket `commerce-files`.
   - Применить Alembic миграции.
2. **Redis**
   - Railway или Render free tier, получить `REDIS_URL`.
3. **Render API**
   - Связать GitHub репозиторий.
   - Build: `pip install -r backend/requirements.txt`.
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. **Render Worker**
   - Build аналогично.
   - Start: `celery -A app.workers.celery_app.celery_app worker --loglevel=info`.
5. **Frontend**
   - GitHub Pages: собрать, поместить в `docs/` или ветку `gh-pages`.
   - Vercel: подключить репозиторий, build command `npm run build`, output `dist`.
6. **Telegram Mini App**
   - В BotFather: `/newbot`, `/newapp`.
   - Web App URL = URL фронтенда.
   - Настроить меню `/setmenubutton`.

## Тестирование и мониторинг

- Health-check: `/healthz`.
- Логи Celery и API доступны в Render dashboard.
- Redis pub/sub можно мониторить через `SUBSCRIBE tasks:updates`.
- При желании подключите Sentry (`SENTRY_DSN` в env).

## Дополнительно

- Существующие скрипты парсинга интегрируются через `LegacyBridge` без переписывания.
- В Celery настроены периодические задачи:
  - чистка Supabase Storage (файлы старше 30 дней),
  - архивация задач (старше 90 дней).
- Экспорт в Google Sheets поддерживает автоматическое предоставление доступа сервисному аккаунту, форматирование и retry с экспоненциальной задержкой.

---

Готово к развертыванию на полностью бесплатном стеке: Supabase (Postgres + Storage), Render/Railway (API, worker, Redis), GitHub Pages/Vercel (frontend), Telegram Bot. Все пути кода и инструкции находятся в этом репозитории. Успехов! 🚀

