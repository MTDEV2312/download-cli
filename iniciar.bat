@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Fijar el directorio de trabajo a la carpeta del script
cd /d "%~dp0"

title Universal Video & Audio Downloader CLI
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
echo      🌐 Universal Video & Audio Downloader CLI
echo       YouTube • TikTok • Instagram • Twitter • Twitch
echo      SoundCloud • Bandcamp • Vimeo • HLS/DASH (1800+)
echo ========================================================
echo.
echo 1.  Descargar Video Universal (YouTube, TikTok, Instagram, Twitter/X, Twitch, etc.)
echo 2.  Descargar Audio de Alta Fidelidad (MP3, FLAC, M4A, OPUS, WAV - YouTube, SoundCloud, Bandcamp, etc.)
echo 3.  Selector Interactivo de Formatos y Resoluciones (-i)
echo 4.  Descargar Lista de Reproducción, Perfil o Álbum
echo 5.  Descarga en Lote Concurrente desde Archivo TXT (Batch)
echo 6.  Ver Información y Formatos de una URL (Info)
echo 7.  Diagnóstico de Cookies y Sesiones de Navegadores
echo 8.  Instalar / Verificar FFmpeg
echo 9.  Actualizar yt-dlp y Dependencias
echo 0.  Salir
echo.
echo ========================================================
echo.

set "opt="
set /p opt="Selecciona una opcion (0-9): "

if "%opt%"=="1" goto dl_video
if "%opt%"=="2" goto dl_audio
if "%opt%"=="3" goto dl_interactive
if "%opt%"=="4" goto dl_playlist
if "%opt%"=="5" goto dl_batch
if "%opt%"=="6" goto info_video
if "%opt%"=="7" goto cookies_menu
if "%opt%"=="8" goto ffmpeg_menu
if "%opt%"=="9" goto update_deps
if "%opt%"=="0" goto exit
if /i "%opt%"=="c" goto cli_free
if /i "%opt%"=="cli" goto cli_free

echo Opcion no valida. Intenta de nuevo.
pause
goto menu

:dl_video
echo.
echo ========================================================
echo   1. Descargar Video Universal
echo ========================================================
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL del video o publicacion: "
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
set "subs_opt="
set /p subs_opt="Descargar e incrustar subtitulos si existen (S/N)? [default: N]: "
set subs_flags=
if /i "%subs_opt%"=="S" set subs_flags=--subtitles --embed-subs --sub-lang es,en,es-419
echo.
set "org_opt="
set /p org_opt="Organizar en subcarpeta por plataforma (ej. Descargas/Videos/TikTok/) (S/N)? [default: S]: "
if "%org_opt%"=="" set org_opt=S
set org_flag=--organize-by-platform
if /i "%org_opt%"=="N" set org_flag=--no-organize-by-platform
echo.
if "!url!"=="" (
    %PY_BIN% youtube_downloader.py download --quality %qual% %subs_flags% %org_flag%
) else (
    %PY_BIN% youtube_downloader.py download "!url!" --quality %qual% %subs_flags% %org_flag%
)
echo.
pause
goto menu

:dl_audio
echo.
echo ========================================================
echo   2. Descargar Audio de Alta Fidelidad
echo ========================================================
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL de la cancion, pista o video: "
echo.
echo Formatos de audio disponibles:
echo [1] MP3  (Recomendado / Maxima compatibilidad con caratula)
echo [2] FLAC (Sin perdida / Lossless - Bandcamp / YouTube)
echo [3] M4A  (AAC de alta fidelidad)
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
    echo [1] 320 kbps (Maxima fidelidad - Recomendado)
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
set "org_opt="
set /p org_opt="Organizar en subcarpeta por plataforma (ej. Descargas/Audios/SoundCloud/) (S/N)? [default: S]: "
if "%org_opt%"=="" set org_opt=S
set org_flag=--organize-by-platform
if /i "%org_opt%"=="N" set org_flag=--no-organize-by-platform
echo.
if "!url!"=="" (
    %PY_BIN% youtube_downloader.py download --audio --audio-format %afmt% --audio-quality %aqual% %org_flag%
) else (
    %PY_BIN% youtube_downloader.py download "!url!" --audio --audio-format %afmt% --audio-quality %aqual% %org_flag%
)
echo.
pause
goto menu

:dl_interactive
echo.
echo ========================================================
echo   3. Selector Interactivo de Formatos y Resoluciones
echo ========================================================
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL del medio a inspeccionar y descargar: "
echo.
set "org_opt="
set /p org_opt="Organizar en subcarpeta por plataforma (S/N)? [default: S]: "
if "%org_opt%"=="" set org_opt=S
set org_flag=--organize-by-platform
if /i "%org_opt%"=="N" set org_flag=--no-organize-by-platform
echo.
if "!url!"=="" (
    %PY_BIN% youtube_downloader.py download -i %org_flag%
) else (
    %PY_BIN% youtube_downloader.py download "!url!" -i %org_flag%
)
echo.
pause
goto menu

:dl_playlist
echo.
echo ========================================================
echo   4. Descargar Lista de Reproducción, Perfil o Álbum
echo ========================================================
echo [Soporta: YouTube Playlists/Canales, SoundCloud Sets, Bandcamp Albums, TikTok Profiles, Twitch VODs]
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL de la lista, perfil o álbum: "
echo.
echo Tipo de descarga:
echo [1] Video (Maxima Calidad / 1080p)
echo [2] Audio (MP3 320k)
echo [3] Audio (FLAC Lossless)
echo.
set "pl_type="
set /p pl_type="Elige tipo [default: 1]: "
if "%pl_type%"=="" set pl_type=1
echo.
set "start_idx="
set /p start_idx="Desde que numero de elemento comenzar? [default: 1]: "
if "%start_idx%"=="" set start_idx=1
echo.
set "skip_err="
set /p skip_err="Continuar si falla algun elemento? (S/N) [default: S]: "
set skip_flag=--skip-errors
if /i "%skip_err%"=="N" set skip_flag=
echo.
set "org_opt="
set /p org_opt="Organizar en subcarpeta por plataforma (S/N)? [default: S]: "
if "%org_opt%"=="" set org_opt=S
set org_flag=--organize-by-platform
if /i "%org_opt%"=="N" set org_flag=--no-organize-by-platform
echo.
if "%pl_type%"=="2" (
    if "!url!"=="" (
        %PY_BIN% youtube_downloader.py playlist --audio --audio-format mp3 --audio-quality 320 --start %start_idx% %skip_flag% %org_flag%
    ) else (
        %PY_BIN% youtube_downloader.py playlist "!url!" --audio --audio-format mp3 --audio-quality 320 --start %start_idx% %skip_flag% %org_flag%
    )
) else if "%pl_type%"=="3" (
    if "!url!"=="" (
        %PY_BIN% youtube_downloader.py playlist --audio --audio-format flac --start %start_idx% %skip_flag% %org_flag%
    ) else (
        %PY_BIN% youtube_downloader.py playlist "!url!" --audio --audio-format flac --start %start_idx% %skip_flag% %org_flag%
    )
) else (
    if "!url!"=="" (
        %PY_BIN% youtube_downloader.py playlist --quality best --start %start_idx% %skip_flag% %org_flag%
    ) else (
        %PY_BIN% youtube_downloader.py playlist "!url!" --quality best --start %start_idx% %skip_flag% %org_flag%
    )
)
echo.
pause
goto menu

:dl_batch
echo.
echo ========================================================
echo   5. Descarga en Lote Concurrente desde Archivo TXT
echo ========================================================
echo Este comando descargara las URLs listadas en un archivo de texto (una URL por linea).
echo Puedes mezclar enlaces de YouTube, TikTok, Instagram, Twitter, Twitch, etc.
echo.
set "batch_file="
set /p batch_file="Archivo de lote [default: examples\urls_ejemplo.txt]: "
if "%batch_file%"=="" set batch_file=examples\urls_ejemplo.txt
if not exist "%batch_file%" (
    if exist "%~dp0%batch_file%" set "batch_file=%~dp0%batch_file%"
)
echo.
echo Tipo de descarga:
echo [1] Video (Mejor calidad disponible)
echo [2] Video (1080p Full HD)
echo [3] Video con Subtitulos (1080p)
echo [4] Audio (MP3 320k)
echo [5] Audio (FLAC Lossless)
echo.
set "batch_type="
set /p batch_type="Selecciona tipo [default: 1]: "
if "%batch_type%"=="" set batch_type=1
echo.
set "concurr="
set /p concurr="Workers concurrentes en paralelo (1-4) [default: 2]: "
if "%concurr%"=="" set concurr=2
echo.
set "org_opt="
set /p org_opt="Organizar en subcarpetas por plataforma (S/N)? [default: S]: "
if "%org_opt%"=="" set org_opt=S
set org_flag=--organize-by-platform
if /i "%org_opt%"=="N" set org_flag=--no-organize-by-platform
echo.
if "%batch_type%"=="5" (
    %PY_BIN% youtube_downloader.py batch "%batch_file%" --audio --audio-format flac --concurrency %concurr% %org_flag%
) else if "%batch_type%"=="4" (
    %PY_BIN% youtube_downloader.py batch "%batch_file%" --audio --audio-format mp3 --audio-quality 320 --concurrency %concurr% %org_flag%
) else if "%batch_type%"=="3" (
    %PY_BIN% youtube_downloader.py batch "%batch_file%" --quality 1080 --subtitles --concurrency %concurr% %org_flag%
) else if "%batch_type%"=="2" (
    %PY_BIN% youtube_downloader.py batch "%batch_file%" --quality 1080 --concurrency %concurr% %org_flag%
) else (
    %PY_BIN% youtube_downloader.py batch "%batch_file%" --quality best --concurrency %concurr% %org_flag%
)
echo.
pause
goto menu

:info_video
echo.
echo ========================================================
echo   6. Ver Información y Formatos de una URL
echo ========================================================
echo [Tip: Si dejas la URL en blanco o pulsas Enter, se usara el Portapapeles si contiene un enlace]
set "url="
set /p url="Introduce la URL del medio a consultar: "
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
echo ========================================================
echo   7. Diagnóstico de Cookies y Sesiones de Navegadores
echo ========================================================
%PY_BIN% youtube_downloader.py cookies
echo.
echo Opciones:
echo [1] Probar descarga autenticada extrayendo cookies de un navegador
echo [2] Volver al Menu Principal
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
        set /p test_url="Introduce URL del video o publicacion para probar: "
        if not "!test_url!"=="" (
            %PY_BIN% youtube_downloader.py download "!test_url!" --cookies-from !bname!
        )
    )
)
echo.
pause
goto menu

:ffmpeg_menu
echo.
echo ========================================================
echo   8. Instalar / Verificar FFmpeg
echo ========================================================
ffmpeg -version >nul 2>&1
if not errorlevel 1 (
    echo [OK] FFmpeg esta correctamente instalado y disponible en PATH:
    ffmpeg -version | findstr /R "ffmpeg version"
    echo.
    echo No se requiere ninguna accion adicional.
) else (
    echo [AVISO] FFmpeg no se detecto en el PATH del sistema.
    echo FFmpeg es necesario para unir audio/video HD y conversion de audio.
    echo.
    echo Deseas intentar instalar FFmpeg ahora con winget?
    set /p ff_inst="Instalar con winget (S/N)? [default: S]: "
    if "%ff_inst%"=="" set ff_inst=S
    if /i "!ff_inst!"=="S" (
        echo.
        echo Ejecutando winget install ffmpeg...
        winget install ffmpeg
        if errorlevel 1 (
            echo.
            echo [ERROR] Fallo la instalacion con winget.
            echo Puedes ejecutar manualmente scripts\instalar_ffmpeg.bat o instalarlo desde https://ffmpeg.org
        ) else (
            echo.
            echo [OK] FFmpeg instalado. Reinicia la terminal si es necesario para refrescar PATH.
        )
    )
)
echo.
pause
goto menu

:update_deps
echo.
echo ========================================================
echo   9. Actualizar yt-dlp y Dependencias del Proyecto
echo ========================================================
echo Actualizando paquetes a sus ultimas versiones compatibles...
echo.
call "%~dp0venv\Scripts\python.exe" -m pip install --upgrade pip yt-dlp yt-dlp-ejs rich click requests mutagen
if errorlevel 1 (
    echo.
    echo [ERROR] Ocurrio un error al actualizar las dependencias.
) else (
    echo.
    echo [OK] Dependencias y extractor yt-dlp actualizados con exito.
)
echo.
pause
goto menu

:cli_free
cls
echo ========================================================
echo   Consola de Comandos Avanzada
echo   Escribe exit para volver al menu principal.
echo ========================================================
echo.
echo Comandos disponibles:
echo   python youtube_downloader.py --help
echo   python youtube_downloader.py download [URL] -i
echo   python youtube_downloader.py download [URL] --organize-by-platform
echo   python youtube_downloader.py download [URL] --audio --audio-format flac
echo   python youtube_downloader.py download [URL] --cookies-from firefox
echo   python youtube_downloader.py cookies
echo   python youtube_downloader.py playlist [URL]
echo   python youtube_downloader.py batch examples\urls_ejemplo.txt --concurrency 3
echo   python youtube_downloader.py clipboard
echo.
cmd /k
goto menu

:exit
exit /b 0
