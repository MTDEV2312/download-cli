@echo off
chcp 65001 >nul
REM Script para configurar el entorno rapidamente en Windows
REM Ejecutar: scripts\setup.bat

REM Fijar directorio de trabajo a la raiz del proyecto (directorio padre de scripts)
cd /d "%~dp0.."

echo.
echo ========================================================
echo   Universal Video & Audio Downloader - Setup
echo ========================================================
echo.

REM Verificar si Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en PATH
    echo Descargalo desde: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Verificar si hay un JavaScript runtime (Node.js o Deno son requeridos por yt-dlp)
set "JS_RUNTIME="
where.exe deno >nul 2>&1 && set "JS_RUNTIME=Deno"
if "%JS_RUNTIME%"=="" (
    where.exe node >nul 2>&1 && set "JS_RUNTIME=Node.js"
)
if "%JS_RUNTIME%"=="" (
    where.exe bun >nul 2>&1 && set "JS_RUNTIME=Bun"
)

if "%JS_RUNTIME%"=="" (
    echo [ADVERTENCIA] No se detecto ningun JavaScript runtime.
    echo YouTube requiere un runtime de JS para descargas de alta resolucion.
    echo Se recomienda instalar Deno: winget install DenoLand.Deno o Node.js.
    echo.
) else (
    echo [OK] Se detecto %JS_RUNTIME% como JavaScript runtime.
)

echo.
echo [1/3] Creando entorno virtual...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual
    pause
    exit /b 1
)

echo [2/3] Activando entorno virtual...
call "%~dp0..\venv\Scripts\activate.bat"

echo [3/3] Instalando dependencias...
call "%~dp0..\venv\Scripts\python.exe" -m pip install --upgrade pip
call "%~dp0..\venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   Setup completado exitosamente!
echo ========================================================
echo.
echo Proximos pasos:
echo 1. Instalar FFmpeg ^(requerido para unir audio/video y calidades altas^)
echo    - Windows: winget install ffmpeg
echo    - O ejecuta: scripts\instalar_ffmpeg.bat
echo.
echo 2. Ejecuta iniciar.bat para abrir el menu interactivo:
echo    - Doble-click en: iniciar.bat
echo.
pause