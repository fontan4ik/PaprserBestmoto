@echo off
chcp 65001 > nul
echo Установка пакетов для Google Sheets экспорта...
echo.

REM Переходим в директорию проекта
cd /d "%~dp0"

REM Проверяем наличие виртуального окружения
if not exist ".venv\Scripts\activate.bat" (
    echo Ошибка: Виртуальное окружение не найдено!
    pause
    exit /b 1
)

REM Активируем виртуальное окружение
echo Активируем виртуальное окружение...
call .venv\Scripts\activate.bat

REM Устанавливаем пакеты
echo Устанавливаем gspread и google-auth...
pip install gspread>=5.12.0 google-auth>=2.23.0

echo.
echo Готово! Пакеты установлены.
echo.
pause

