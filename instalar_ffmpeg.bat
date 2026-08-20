@echo off
chcp 65001 >nul
REM Script para instalar FFmpeg en Windows

REM Fijar directorio de trabajo al directorio del script
cd /d "%~dp0"

echo.
echo ========================================
echo   Instalador de FFmpeg
echo ========================================
echo.

REM Verificar si FFmpeg ya esta instalado
ffmpeg -version >nul 2>&1
if errorlevel 1 goto install_ffmpeg

echo [OK] FFmpeg ya esta instalado!
ffmpeg -version | findstr /R "ffmpeg version"
goto end

:install_ffmpeg
echo [INFO] FFmpeg no esta instalado.
echo.
echo Metodos de instalacion:
echo.
echo 1. Usando Windows Package Manager - winget (Recomendado)
echo    Ejecuta: winget install ffmpeg
echo.
echo 2. Usando Chocolatey
echo    Ejecuta: choco install ffmpeg
echo.
echo 3. Descarga manual
echo    Ve a: https://ffmpeg.org/download.html
echo.

set /p install="Deseas intentar instalar FFmpeg ahora con winget? (S/N): "
if /i not "%install%"=="S" (
    echo.
    echo Por favor instala FFmpeg manualmente y vuelve a intentar.
    goto end
)

echo.
echo Instalando FFmpeg con winget...
winget install ffmpeg
if errorlevel 1 (
    echo.
    echo [ERROR] No se pudo instalar con winget.
    echo Por favor descargalo manualmente desde https://ffmpeg.org/download.html
    echo o ejecuta en una terminal como administrador: winget install ffmpeg
)

:end
echo.
echo ========================================
echo Fin del instalador
echo ========================================
echo.
pause