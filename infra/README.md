# Infra & Deployment Playbook

## 1. Supabase (PostgreSQL + Storage)

1. Создайте проект на [supabase.com](https://supabase.com) (Free Tier).
2. В Settings → Database скопируйте **Connection string** → переменная `DATABASE_URL`.
3. Storage → создайте bucket `commerce-files` с public access = `False`.
4. В разделе SQL Editor:
   ```sql
   -- включить расширения (если недоступно по умолчанию)
   create extension if not exists "uuid-ossp";
   create extension if not exists "pgcrypto";
   ```
5. В репозитории выполните миграции: `alembic upgrade head`.
6. Настройте Row Level Security (RLS) при необходимости (Supabase Dashboard → Policies) для каждой таблицы.

## 2. Redis (Railway или Render)

- Railway: New Project → Redis. Скопируйте `redis://` строку → `REDIS_URL`.
- Render: Blueprint Marketplace → Redis → `External Connection`.

## 3. Render: API + Worker

Создайте файл `render.yaml` в корне (готовый пример — `infra/render.yaml`) и подключите репозиторий в Render.

### API service

- Type: Web Service.
- Build Command: `pip install -r backend/requirements.txt`.
- Start Command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Environment: Python 3.11.
- Variables: заполните все из `backend/env.example`.

### Worker service

- Type: Background Worker.
- Build Command: такой же.
- Start Command: `cd backend && celery -A app.workers.celery_app.celery_app worker --loglevel=info`.
- В Variables продублируйте env.

## 4. Frontend (GitHub Pages или Vercel)

### GitHub Pages

1. `npm run build` в `frontend/`.
2. Скопируйте `dist/` в `docs/` или используйте action для gh-pages.
3. Settings → Pages → deploy from branch (`gh-pages` или `/docs`).

### Vercel

1. Подключите репозиторий.
2. Framework: Vite.
3. Build Command: `npm run build`.
4. Output: `frontend/dist`.
5. Env: `VITE_API_BASE_URL=https://<render-api>.onrender.com`.

## 5. Telegram Bot & Mini App

1. В BotFather: `/newbot` → получите `TELEGRAM_BOT_TOKEN`.
2. `/newapp` → Web App URL = фронтенд (HTTPS обязателен).
3. `/setmenubutton` → ссылка на Mini App.
4. Сохраните `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `INITIAL_ADMIN_TELEGRAM_ID` в env.

## 6. Google Sheets

1. Создайте Service Account в Google Cloud (`parser-bestmoto`).
2. Скачайте JSON, закодируйте base64 → `GOOGLE_CREDENTIALS`.
3. Email сервисного аккаунта: `vladimir@parser-bestmoto.iam.gserviceaccount.com`.
4. Дайте доступ к нужным таблицам или позвольте приложению делать это автоматически (Drive API).

## 7. Переменные окружения (обязательно)

| Variable | Описание |
| --- | --- |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `INITIAL_ADMIN_TELEGRAM_ID` | Telegram bot |
| `DATABASE_URL` | Supabase connection string |
| `REDIS_URL` | Railway/Render Redis |
| `GOOGLE_CREDENTIALS`, `GOOGLE_SERVICE_ACCOUNT_EMAIL` | Google Sheets |
| `FRONTEND_URL`, `API_BASE_URL` | Публичные URL |
| `SECRET_KEY` | Любая случайная строка |
| Rate limits (`USER_RATE_LIMIT`, `ADMIN_RATE_LIMIT`, `MAX_FILE_SIZE_MB`, …) | См. env.example |

## 8. Health-check & мониторинг

- API health: `GET /healthz` (без проверки initData).
- Celery worker: Render logs.
- Redis pub/sub: `SUBSCRIBE tasks:updates`.
- (Опционально) добавьте Sentry (`SENTRY_DSN`).

## 9. CI/CD идеи

- GitHub Actions: lint + tests → deploy to Render via `render.yaml`.
- Configure `frontend` build pipeline → GitHub Pages (actions/gh-pages) или Vercel auto deploy.

Следуя этой инструкции, можно поднять полный стек на бесплатных тарифах без ручных правок кода. Удачи! 🚀

