# Исправление ошибки ModuleNotFoundError: No module named 'distutils'

## Проблема
В Python 3.12+ модуль `distutils` был удален, но `undetected-chromedriver` все еще его использует.

## Решение

### Вариант 1: Установка setuptools в виртуальное окружение (рекомендуется)

1. Откройте командную строку или PowerShell
2. Активируйте виртуальное окружение:
   ```powershell
   .venv\Scripts\activate
   ```
3. Установите setuptools:
   ```powershell
   pip install setuptools --upgrade
   ```
4. Проверьте:
   ```powershell
   python -c "import distutils; print('OK')"
   ```

### Вариант 2: Использование глобального Python (если venv не работает)

Если виртуальное окружение не работает, можно использовать глобальный Python:

1. Установите setuptools глобально:
   ```powershell
   python -m pip install setuptools --upgrade
   ```
2. Запустите сервер:
   ```powershell
   python server.py
   ```

### Вариант 3: Обновление undetected-chromedriver

Попробуйте обновить до последней версии:

```powershell
pip install --upgrade undetected-chromedriver
```

## После исправления

Запустите сервер:
```powershell
python server.py
```

Сервер должен запуститься без ошибок и быть доступен по адресу:
http://localhost:5000

