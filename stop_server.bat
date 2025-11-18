@echo off
chcp 65001 > nul
title Остановка сервера

echo.
echo ============================================================
echo           🛑 Остановка сервера конкурентного анализа
echo ============================================================
echo.

echo 🔍 Ищем процессы Python...
tasklist | findstr python.exe > nul
if %errorlevel% equ 0 (
    echo ✅ Найдены процессы Python
    echo.
    echo 🛑 Останавливаем все процессы Python...
    taskkill /F /IM python.exe /T
    taskkill /F /IM pythonw.exe /T > nul 2>&1
) else (
    echo ℹ️  Процессы Python не найдены
)
echo.

echo 🔍 Ищем процессы Chrome...
tasklist | findstr chrome.exe > nul
if %errorlevel% equ 0 (
    echo ✅ Найдены процессы Chrome
    echo.
    echo 🛑 Останавливаем Chrome и ChromeDriver...
    taskkill /F /IM chrome.exe /T > nul 2>&1
    taskkill /F /IM chromedriver.exe /T > nul 2>&1
) else (
    echo ℹ️  Процессы Chrome не найдены
)
echo.

echo 🔍 Проверяем порт 5000...
netstat -ano | findstr ":5000" | findstr "LISTENING" > nul
if %errorlevel% equ 0 (
    echo ⚠️  Порт 5000 занят, освобождаем...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000" ^| findstr "LISTENING"') do (
        echo    Останавливаем процесс PID: %%a
        taskkill /F /PID %%a
    )
) else (
    echo ✅ Порт 5000 свободен
)
echo.

timeout /t 2 /nobreak > nul

echo ============================================================
echo ✅ Все процессы остановлены
echo ============================================================
echo.
pause

