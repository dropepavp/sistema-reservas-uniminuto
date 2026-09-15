@echo off
chcp 65001 > nul
title Sistema Integrado UNIMINUTO - Ejecutar Proyecto

cd /d "%~dp0"

echo ============================================================
echo   Iniciando Proyecto Sistema Integrado UNIMINUTO
echo ============================================================
echo.

REM 1. Verificar entorno virtual
if not exist ".venv" (
    echo [1/3] Creando entorno virtual Python (.venv)...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

REM 2. Activar entorno virtual
call .\.venv\Scripts\activate.bat

REM 3. Instalar dependencias si hace falta
echo [2/3] Verificando dependencias...
pip install -r requirements.txt --quiet

REM 4. Ejecutar servidor Flask
echo [3/3] Iniciando servidor Flask...
echo.
echo Servidor en: http://127.0.0.1:5000
echo Presiona CTRL+C para detener el servidor.
echo ============================================================
echo.

python run.py

pause