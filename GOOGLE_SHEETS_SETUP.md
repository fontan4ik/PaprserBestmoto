# Настройка экспорта в Google Таблицы

## Требования

1. **Service Account в Google Cloud Console**
2. **JSON файл с credentials** (должен называться `credentials.json` и находиться в корне проекта)
3. **Google Таблица** с предоставленным доступом для Service Account

## Шаги настройки

### 1. Создание Service Account

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Перейдите в **APIs & Services** → **Credentials**
4. Нажмите **Create Credentials** → **Service Account**
5. Заполните данные и создайте Service Account
6. Скачайте JSON ключ и сохраните его как `credentials.json` в корне проекта

### 2. Включение Google Sheets API

1. В Google Cloud Console перейдите в **APIs & Services** → **Library**
2. Найдите **Google Sheets API** и включите его
3. Найдите **Google Drive API** и включите его

### 3. Предоставление доступа к таблице

1. Откройте вашу Google Таблицу
2. Нажмите **Поделиться** (Share)
3. Добавьте email вашего Service Account (находится в JSON файле, поле `client_email`)
4. Дайте права **Редактор** (Editor)

### 4. Получение ID таблицы

ID таблицы находится в URL:
```
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
```

Скопируйте `SPREADSHEET_ID` - это и есть ID таблицы.

## Использование

1. Запустите анализ в системе
2. Нажмите кнопку **"Экспорт в Google"**
3. Введите ID таблицы (или полный URL)
4. Данные будут экспортированы в указанную таблицу

## Примечания

- Таблица будет полностью очищена перед записью новых данных
- Данные записываются в лист `Sheet1` (по умолчанию)
- Структура данных соответствует CSV экспорту

