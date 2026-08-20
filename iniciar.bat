@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Fijar el directorio de trabajo a la carpeta del script
cd /d "%~dp0"

title YouTube Video Downloader CLI
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM Verificar si el entorno virtual existe. Si no, crearlo automaticamente (Plug and Play)
if exist "%~dp0venv\Scripts\python.exe" goto venv_ready

echo ========================================================
echo   Configuracion inicial detectada - Plug and Play
echo   Creando entorno virtual e instalando dependencias...
echo ========================================================
echo.

set "PYTHON_EXE="
where.exe python >nul 2>&1 && set "PYTHON_EXE=python"
if "%PYTHON_EXE%"=="" (
    where.exe py >nul 2>&1 && set "PYTHON_EXE=py"
)

if "%PYTHON_EXE%"=="" (
    echo [ERROR] No se encontro Python en el sistema.
    echo Descargalo e instalalo desde: https://www.python.org/downloads/
    echo Asegurate de marcar la casilla "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

echo [1/2] Creando entorno virtual...
%PYTHON_EXE% -m venv venv
if errorlevel 1 (
    echo [ERROR] Fallo la creacion del entorno virtual.
    pause
    exit /b 1
)

echo [2/2] Instalando librerias necesarias...
call "%~dp0venv\Scripts\python.exe" -m pip install --upgrade pip
call "%~dp0venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de dependencias.
    pause
    exit /b 1
)
echo.
echo [OK] Entorno listo. Iniciando aplicacion...
echo.

:venv_ready
REM Activar entorno virtual
call "%~dp0venv\Scripts\activate.bat"
set PY_BIN="%~dp0venv\Scripts\python.exe"

:menu
cls
echo ========================================================
echo          YouTube Video Downloader CLI - Menu
echo ========================================================
echo.
echo 1.  Descargar Video (Modo Rapido: Maxima Calidad / 1080p / 4K)
echo 2.  Descargar Video con Selector Interactivo de Resoluciones (-i)
echo 3.  Descargar Video con Subtitulos (.srt / incrustados)
echo 4.  Descargar Video (Solo Audio: MP3 320k, FLAC, M4A, OPUS)
echo 5.  Descargar Playlist Completa (Video)
echo 6.  Descargar Playlist (Solo Audio: MP3 320k, FLAC, M4A, OPUS)
echo 7.  Comprobar / Descargar URL desde el Portapapeles
echo 8.  Descargar lista de videos en lote (batch) desde urls_ejemplo.txt
echo 9.  Ver formatos y calidades disponibles de un video (Info)
echo 10. Diagnosticar / Configurar Cookies de YouTube (Anti-Bot / 403)
echo 11. Consola de Comandos Avanzada (Acceso CLI libre)
echo 12. Salir
echo.
echo ========================================================
echo.

set "opt="
set /p opt="Selecciona una opcion (1-12): "

if "%opt%"=="1" goto dl_video
if "%opt%"=="2" goto dl_interactive
if "%opt%"=="3" goto dl_subtitles
if "%opt%"=="4" goto dl_audio
if "%opt%"=="5" goto dl_playlist
if "%opt%"=="6" goto dl_playlist_audio
if "%opt%"=="7" goto dl_clipboard
if "%opt%"=="8" goto dl_batch
if "%opt%"=="9" goto info_video
if "%opt%"=="10" goto cookies_menu
if "%opt%"=="11" goto cli_free
if "%opt%"=="12" goto exit

echo Opcion no valida. Intenta de nuevo.
pause
goto menu

:dl_video
echo.
echo --- Descargar Video (Modo Rapido) ---
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL del video: "
echo.
echo Calidades disponibles:
echo [best] Maxima calidad disponible (incluye 4K/2K si estan disponibles)
echo [1080] Full HD (1080p)
echo [720]  HD (720p)
echo.
set "qual="
set /p qual="Elige calidad [default: best]: "
if "%qual%"=="" set qual=best
echo.
if "!url!"=="" (
    %PY_BIN% youtube_downloader.py download --quality %qual%
) else (
    %PY_BIN% youtube_downloader.py download "!url!" --quality %qual%
)
echo.
pause
goto menu

:dl_interactive
echo.
echo --- Descargar Video con Selector Interactivo de Resoluciones ---
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL del video: "
echo.
if "!url!"=="" (
    %PY_BIN% youtube_downloader.py download -i
) else (
    %PY_BIN% youtube_downloader.py download "!url!" -i
)
echo.
pause
goto menu

:dl_subtitles
echo.
echo --- Descargar Video con Subtitulos ---
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL del video: "
echo.
echo Calidades disponibles:
echo [best] Maxima calidad disponible
echo [1080] Full HD (1080p)
echo [720]  HD (720p)
echo.
set "qual="
set /p qual="Elige calidad [default: best]: "
if "%qual%"=="" set qual=best
echo.
set "sublang="
set /p sublang="Idiomas de subtitulos [default: es,en,es-419]: "
if "%sublang%"=="" set sublang=es,en,es-419
echo.
set "embed_opt="
set /p embed_opt="Incrustar subtitulos en el contenedor del video (S/N)? [default: S]: "
set embed_flag=--embed-subs
if /i "%embed_opt%"=="N" set embed_flag=--write-subs
echo.
if "!url!"=="" (
    %PY_BIN% youtube_downloader.py download --quality %qual% --subtitles --sub-lang "%sublang%" %embed_flag%
) else (
    %PY_BIN% youtube_downloader.py download "!url!" --quality %qual% --subtitles --sub-lang "%sublang%" %embed_flag%
)
echo.
pause
goto menu

:dl_audio
echo.
echo --- Descargar Video en Audio ---
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL del video: "
echo.
echo Formatos de audio disponibles:
echo [1] MP3  (Recomendado / Maxima compatibilidad con caratula)
echo [2] FLAC (Sin perdida / Lossless)
echo [3] M4A  (AAC de alta calidad)
echo [4] OPUS (Mayor fidelidad y compresion)
echo [5] WAV  (Audio sin comprimir)
echo.
set "afmt_opt="
set /p afmt_opt="Elige formato [default: 1]: "
if "%afmt_opt%"=="" set afmt_opt=1

set afmt=mp3
if "%afmt_opt%"=="1" set afmt=mp3
if "%afmt_opt%"=="2" set afmt=flac
if "%afmt_opt%"=="3" set afmt=m4a
if "%afmt_opt%"=="4" set afmt=opus
if "%afmt_opt%"=="5" set afmt=wav

set aqual=320
if "%afmt%"=="mp3" (
    echo.
    echo Calidad / Bitrate para MP3:
    echo [1] 320 kbps (Maxima calidad - Recomendado)
    echo [2] 256 kbps (Muy alta calidad)
    echo [3] 192 kbps (Calidad estandar)
    echo [4] 128 kbps (Ahorro de espacio)
    echo.
    set "aqual_opt="
    set /p aqual_opt="Elige bitrate [default: 1]: "
    if "%aqual_opt%"=="" set aqual_opt=1
    if "%aqual_opt%"=="1" set aqual=320
    if "%aqual_opt%"=="2" set aqual=256
    if "%aqual_opt%"=="3" set aqual=192
    if "%aqual_opt%"=="4" set aqual=128
)
echo.
if "!url!"=="" (
    %PY_BIN% youtube_downloader.py download --audio --audio-format %afmt% --audio-quality %aqual%
) else (
    %PY_BIN% youtube_downloader.py download "!url!" --audio --audio-format %afmt% --audio-quality %aqual%
)
echo.
pause
goto menu

:dl_playlist
echo.
echo --- Descargar Playlist Completa ---
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL de la playlist: "
echo.
echo Calidades disponibles:
echo [best] Maxima calidad disponible
echo [1080] Full HD (1080p)
echo [720]  HD (720p)
echo.
set "qual="
set /p qual="Elige calidad [default: best]: "
if "%qual%"=="" set qual=best
echo.
set "start_idx="
set /p start_idx="Desde que numero de video comenzar? [default: 1]: "
if "%start_idx%"=="" set start_idx=1
echo.
set "skip_err="
set /p skip_err="Continuar si falla algun video? (S/N) [default: N]: "
set skip_flag=
if /i "%skip_err%"=="S" set skip_flag=--skip-errors
echo.
if "!url!"=="" (
    %PY_BIN% youtube_downloader.py playlist --quality %qual% --start %start_idx% %skip_flag%
) else (
    %PY_BIN% youtube_downloader.py playlist "!url!" --quality %qual% --start %start_idx% %skip_flag%
)
echo.
pause
goto menu

:dl_playlist_audio
echo.
echo --- Descargar Playlist en Audio ---
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL de la playlist: "
echo.
echo Formatos de audio disponibles:
echo [1] MP3  (Recomendado / Maxima compatibilidad)
echo [2] FLAC (Sin perdida / Lossless)
echo [3] M4A  (AAC de alta calidad)
echo [4] OPUS (Mayor fidelidad y compresion)
echo [5] WAV  (Audio sin comprimir)
echo.
set "afmt_opt="
set /p afmt_opt="Elige formato [default: 1]: "
if "%afmt_opt%"=="" set afmt_opt=1

set afmt=mp3
if "%afmt_opt%"=="1" set afmt=mp3
if "%afmt_opt%"=="2" set afmt=flac
if "%afmt_opt%"=="3" set afmt=m4a
if "%afmt_opt%"=="4" set afmt=opus
if "%afmt_opt%"=="5" set afmt=wav

set aqual=320
if "%afmt%"=="mp3" (
    echo.
    echo Calidad / Bitrate para MP3:
    echo [1] 320 kbps (Maxima calidad - Recomendado)
    echo [2] 256 kbps (Muy alta calidad)
    echo [3] 192 kbps (Calidad estandar)
    echo [4] 128 kbps (Ahorro de espacio)
    echo.
    set "aqual_opt="
    set /p aqual_opt="Elige bitrate [default: 1]: "
    if "%aqual_opt%"=="" set aqual_opt=1
    if "%aqual_opt%"=="1" set aqual=320
    if "%aqual_opt%"=="2" set aqual=256
    if "%aqual_opt%"=="3" set aqual=192
    if "%aqual_opt%"=="4" set aqual=128
)
echo.
set "start_idx="
set /p start_idx="Desde que numero de video comenzar? [default: 1]: "
if "%start_idx%"=="" set start_idx=1
echo.
set "skip_err="
set /p skip_err="Continuar si falla algun video? (S/N) [default: N]: "
set skip_flag=
if /i "%skip_err%"=="S" set skip_flag=--skip-errors
echo.
if "!url!"=="" (
    %PY_BIN% youtube_downloader.py playlist --audio --audio-format %afmt% --audio-quality %aqual% --start %start_idx% %skip_flag%
) else (
    %PY_BIN% youtube_downloader.py playlist "!url!" --audio --audio-format %afmt% --audio-quality %aqual% --start %start_idx% %skip_flag%
)
echo.
pause
goto menu

:dl_clipboard
echo.
echo --- Descargar desde el Portapapeles ---
%PY_BIN% youtube_downloader.py clipboard
echo.
echo Opciones de descarga para la URL detectada:
echo [1] Descargar Video con Selector Interactivo (-i)
echo [2] Descargar Video (Maxima calidad)
echo [3] Descargar Video (1080p)
echo [4] Descargar Audio (MP3 320k)
echo [5] Ver Informacion y Formatos
echo [6] Volver al Menu
echo.
set "c_opt="
set /p c_opt="Selecciona opcion [default: 1]: "
if "%c_opt%"=="" set c_opt=1

if "%c_opt%"=="1" %PY_BIN% youtube_downloader.py download --clipboard -i
if "%c_opt%"=="2" %PY_BIN% youtube_downloader.py download --clipboard --quality best
if "%c_opt%"=="3" %PY_BIN% youtube_downloader.py download --clipboard --quality 1080
if "%c_opt%"=="4" %PY_BIN% youtube_downloader.py download --clipboard --audio --audio-format mp3 --audio-quality 320
if "%c_opt%"=="5" %PY_BIN% youtube_downloader.py info --clipboard
if "%c_opt%"=="6" goto menu
echo.
pause
goto menu

:dl_batch
echo.
echo --- Descargar en Lote Concurrente (batch) ---
echo Este comando descargara las URLs listadas en urls_ejemplo.txt.
echo Si quieres usar tu propia lista, edita o crea ese archivo (una URL por linea).
echo.
set "batch_file="
set /p batch_file="Archivo de lote [default: urls_ejemplo.txt]: "
if "%batch_file%"=="" set batch_file=urls_ejemplo.txt
echo.
echo Tipo de descarga:
echo [1] Video (Mejor calidad)
echo [2] Video (1080p)
echo [3] Video con Subtitulos (1080p)
echo [4] Audio (MP3 320k)
echo.
set "batch_type="
set /p batch_type="Selecciona tipo [default: 1]: "
if "%batch_type%"=="" set batch_type=1
echo.
set "concurr="
set /p concurr="Workers concurrentes en paralelo (1-4) [default: 2]: "
if "%concurr%"=="" set concurr=2
echo.
if "%batch_type%"=="4" (
    %PY_BIN% youtube_downloader.py batch "%batch_file%" --audio --audio-format mp3 --audio-quality 320 --concurrency %concurr%
) else if "%batch_type%"=="3" (
    %PY_BIN% youtube_downloader.py batch "%batch_file%" --quality 1080 --subtitles --concurrency %concurr%
) else if "%batch_type%"=="2" (
    %PY_BIN% youtube_downloader.py batch "%batch_file%" --quality 1080 --concurrency %concurr%
) else (
    %PY_BIN% youtube_downloader.py batch "%batch_file%" --quality best --concurrency %concurr%
)
echo.
pause
goto menu

:info_video
echo.
echo --- Ver Informacion y Formatos de Video ---
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL del video: "
echo.
if "!url!"=="" (
    %PY_BIN% youtube_downloader.py info
) else (
    %PY_BIN% youtube_downloader.py info "!url!"
)
echo.
pause
goto menu

:cookies_menu
echo.
echo --- Diagnostico y Configuracion de Cookies ---
%PY_BIN% youtube_downloader.py cookies
echo.
echo Opciones de Cookies:
echo [1] Probar descarga usando cookies de un navegador
echo [2] Volver al Menu
echo.
set "ck_opt="
set /p ck_opt="Selecciona una opcion [default: 2]: "
if "%ck_opt%"=="" set ck_opt=2

if "%ck_opt%"=="1" (
    echo.
    set "bname="
    set /p bname="Escribe el nombre del navegador (firefox, brave, chrome, edge, opera): "
    if not "!bname!"=="" (
        set "test_url="
        set /p test_url="Introduce URL del video para probar: "
        if not "!test_url!"=="" (
            %PY_BIN% youtube_downloader.py download "!test_url!" --cookies-from !bname!
        )
    )
)
echo.
pause
goto menu

:cli_free
cls
echo ========================================================
echo   Consola de Comandos Avanzada
echo   Escribe deactivate para salir del entorno virtual.
echo   Escribe exit para volver al menu.
echo ========================================================
echo.
echo Comandos disponibles:
echo   python youtube_downloader.py --help
echo   python youtube_downloader.py download [URL] -i
echo   python youtube_downloader.py download [URL] --subtitles --sub-lang es,en
echo   python youtube_downloader.py download [URL] --cookies-from firefox
echo   python youtube_downloader.py cookies
echo   python youtube_downloader.py playlist [URL]
echo   python youtube_downloader.py clipboard
echo.
cmd /k
goto menu

:exit
exit /b 0
