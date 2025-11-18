@echo off
chcp 65001 > nul
title Проверка сервера

echo.
echo ============================================================
echo           🔍 Проверка состояния сервера
echo ============================================================
echo.

echo 📊 Процессы Python:
tasklist | findstr python.exe
if %errorlevel% neq 0 (
    echo    ❌ Не найдено
)
echo.

echo 📊 Процессы Chrome:
tasklist | findstr chrome.exe
if %errorlevel% neq 0 (
    echo    ❌ Не найдено
)
echo.

echo 📊 Порт 5000:
netstat -ano | findstr ":5000"
if %errorlevel% neq 0 (
    echo    ✅ Свободен
)
echo.

echo 🌐 Попытка подключения к серверу...
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:5000' -TimeoutSec 3; Write-Host '✅ Сервер доступен' -ForegroundColor Green } catch { Write-Host '❌ Сервер недоступен' -ForegroundColor Red }"
echo.

echo ============================================================
pause

