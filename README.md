# 🌐 Universal Video & Audio Downloader CLI

> **Descargador Universal de Medios Multimedia de Alta Fidelidad**  
> Compatible con **YouTube, TikTok, Instagram, Twitter/X, Twitch, SoundCloud, Bandcamp, Vimeo, Facebook, Reddit, Kick**, streams directos **HLS (`.m3u8`) / DASH (`.mpd`)** y más de **1800+ sitios web** soportados por `yt-dlp`.

---

## 🌟 Características Principales

- 🌐 **Soporte Multi-Plataforma Universal**: Extracción optimizada para más de 1800 servicios web y streams HTML5 directos.
- ⚡ **Descargas Concurrentes Multihilo**: Soporte multihilo para listas en lote (`batch`) con `ThreadPoolExecutor` (`--concurrency` / `-w`) y fragmentación paralela acelerada (`concurrent_fragment_downloads = 6`).
- 📁 **Organización Inteligente por Plataforma**: Subcarpetas automáticas (`--organize-by-platform`) en `Descargas/Videos/TikTok/`, `Descargas/Audios/SoundCloud/`, etc.
- 🛡️ **Protección Anti-Bloqueo Inteligente**: Pausas adaptativas con jitter aleatorio (`--delay` / `-d ±0.5s`) y soporte multi-cliente para evitar límites de tasa (rate-limiting).
- 🎨 **Interfaz de Terminal Moderna con Rich**: Barras de progreso con métricas de velocidad en tiempo real (MB/s), tamaño descargado/total, ETA preciso y progreso dual para playlists y lotes concurrentes.
- 🔍 **Selector Interactivo de Formatos (`-i`)**: Tabla interactiva con resoluciones reales (8K, 4K, 1440p, 1080p60, 720p, etc.), tasas de cuadros (fps) y tamaños estimados.
- 🎵 **Audio de Alta Fidelidad**: Conversión a MP3 (320, 256, 192, 128 kbps), FLAC (Lossless sin pérdida), M4A (AAC), OPUS y WAV, con carátula y metadatos incrustados.
- 📝 **Subtítulos y Transcripciones**: Descarga e incrustación directa de subtítulos manuales y autogenerados (`--subtitles`, `--sub-lang`, `--embed-subs`).
- 🍪 **Gestión Multi-Sitio de Cookies y Sesiones**: Detección automática en navegadores (`brave`, `chrome`, `edge`, `firefox`, `opera`) o archivos de cookies en cascada (`cookies_[plataforma].txt` -> `cookies.txt` -> `youtube_cookies.txt`).
- 📋 **Portapapeles Universal**: Detección automática de enlaces copiados en el portapapeles sin importar la red social.
- 🔔 **Notificaciones Nativas de Escritorio (Toast)**: Alertas al finalizar descargas largas con acceso directo a la carpeta de archivos.
- 📦 **Historial y Prevención de Re-descargas**: Registro automático en `.download_archive.txt` para evitar duplicar descargas.

---

## 📚 Documentación y Guías

Para información detallada y especificaciones técnicas, consulta la carpeta `docs/`:

| Documento | Descripción |
| :--- | :--- |
| 🚀 **[Guía de Inicio Rápido](file:///D:/videos/dowloaderVid/docs/INICIO_RAPIDO.md)** | Ejemplos rápidos de uso por plataforma y guía del menú interactivo. |
| 📦 **[Guía de Instalación Detallada](file:///D:/videos/dowloaderVid/docs/INSTALACION.md)** | Instalación de Python, FFmpeg, Deno/Node.js y resolución de dependencias. |
| 🏗️ **[Análisis de Descarga Universal](file:///D:/videos/dowloaderVid/docs/ANALISIS_DESCARGA_UNIVERSAL.md)** | Arquitectura del sistema, extractores y soporte multi-red social. |
| ⚡ **[Análisis de Optimizaciones y Mejoras](file:///D:/videos/dowloaderVid/docs/ANALISIS_MEJORAS.md)** | Diagnóstico de rendimiento, concurrencia y prevención de bloqueos. |

---

## 📱 Plataformas Principales Soportadas

| Plataforma | Tipo de Contenidos Soportados | Capacidades Especiales | Necesidad de Cookies |
| :--- | :--- | :--- | :--- |
| 🔴 **YouTube** | Videos, Shorts, Lives, Playlists, Canales, Music | Extracción 4K/8K, subtítulos multilingües, bypass JS | Opcional (salvo restricción de edad/403) |
| 🎵 **TikTok** | Videos, Sonidos/Audios, Perfiles, Feeds | Descarga **sin marca de agua** en HD original | No (salvo cuentas privadas) |
| 📸 **Instagram** | Reels, Stories, Posts, Carruseles, IGTV | Extracción de streams directos en máxima calidad | Recomendado para Stories y cuentas privadas |
| 🐦 **Twitter / X** | Videos nativos, Clips, Hilos, GIFs | Múltiples bitrates MP4 (H.264), transmisiones en vivo | Opcional (recomendado para NSFW / privados) |
| 🟣 **Twitch** | VODs, Clips pasados, Streams en Vivo | Selección de calidades (1080p60 Source, 720p60, etc.) | Opcional (salvo VODs sub-only) |
| ☁️ **SoundCloud** | Pistas individuales, Álbumes, Sets, Playlists | Audio HQ, metadatos ID3 completos y carátula | No |
| 🎸 **Bandcamp** | Canciones, Discografías, Álbumes | Flujos directos MP3/FLAC con carátula y metadatos | No |
| 🔷 **Vimeo** | Videos HD/4K, Showcases, Canales | Selección de bitrate adaptable y subtítulos | Opcional |
| 🔵 **Facebook** | Videos públicos/privados, Reels, Watch | Extracción en HD y SD | Opcional (públicos) / Requerido (privados) |
| 🟠 **Reddit** | Videos en `v.redd.it`, posts multimedia | Fusión automática de pistas de video y audio | No |
| 🟢 **Kick** | Clips, VODs, Transmisiones en directo | Soporte de HLS con fragmentos paralelos | No |
| 📡 **Streams Directos** | Manifiestos HLS (`.m3u8`), DASH (`.mpd`), MP4 | Descarga fragmentada paralela con remuxing FFmpeg | No |
| 🌐 **1800+ Sitios Web** | Reproductores HTML5, Video.js, JWPlayer | Extractor genérico con heurística de video/audio | No |

---

## 🚀 Instalación Rápida

### Windows (Automática - Plug and Play)
1. Haz doble-click en **[iniciar.bat](file:///D:/videos/dowloaderVid/iniciar.bat)**.
2. El script creará automáticamente el entorno virtual e instalará todas las dependencias necesarias.

### Dependencias Externas Recomendadas
1. **FFmpeg** (Requerido para unir audio/video HD y conversión de audio):
   ```powershell
   winget install ffmpeg
   ```
   * O ejecuta el instalador asistido: [scripts/instalar_ffmpeg.bat](file:///D:/videos/dowloaderVid/scripts/instalar_ffmpeg.bat).
2. **Deno o Node.js** (Recomendado para resolver challenges de YouTube):
   ```powershell
   winget install DenoLand.Deno
   # o
   winget install OpenJS.NodeJS
   ```

---

## 💻 Guía de Uso CLI (Línea de Comandos)

### 1. Descarga Básica o con Selector Interactivo
```bash
# Detecta automáticamente la URL del portapapeles
python youtube_downloader.py download

# Selector interactivo de calidades y formatos reales (-i)
python youtube_downloader.py download "https://www.tiktok.com/@user/video/123456789" -i

# Descarga organizando automáticamente en subcarpeta por plataforma
python youtube_downloader.py download "https://www.instagram.com/reel/C123456789/" --organize-by-platform
```

### 2. Descarga de Video en Calidad Específica con Subtítulos
```bash
# Video en 1080p con subtítulos incrustados en español e inglés
python youtube_downloader.py download "URL" --quality 1080 --subtitles --sub-lang es,en --embed-subs

# Video en máxima resolución disponible (incluye 4K / 8K)
python youtube_downloader.py download "URL" --quality best
```

### 3. Descarga de Solo Audio en Alta Fidelidad
```bash
# MP3 a 320 kbps con carátula y metadatos incrustados
python youtube_downloader.py download "https://soundcloud.com/artist/track" --audio --audio-format mp3 --audio-quality 320

# Audio FLAC Lossless sin pérdida (Bandcamp / YouTube)
python youtube_downloader.py download "https://artist.bandcamp.com/track/song" --audio --audio-format flac

# Audio AAC/M4A u OPUS
python youtube_downloader.py download "URL" --audio --audio-format m4a
```

### 4. Descarga de Playlists, Álbumes o Perfiles
```bash
# Descargar playlist o set de SoundCloud
python youtube_downloader.py playlist "https://soundcloud.com/artist/sets/album" --audio --audio-format mp3

# Descargar canal o playlist de YouTube desde el elemento #5
python youtube_downloader.py playlist "URL_PLAYLIST" --quality 1080 --start 5 --skip-errors
```

### 5. Descarga en Lote Concurrente (Batch)
```bash
# Descargar lista de URLs en paralelo con 3 workers y pausa anti-bloqueo
python youtube_downloader.py batch examples/urls_ejemplo.txt --concurrency 3 --delay 1.0 --organize-by-platform
```

### 6. Inspección de Información y Diagnóstico de Cookies
```bash
# Ver tabla con todos los streams y formatos de una URL
python youtube_downloader.py info "URL"

# Diagnóstico de sesiones de navegadores y archivos de cookies
python youtube_downloader.py cookies

# Descargar usando sesión de navegador para contenido restringido
python youtube_downloader.py download "URL" --cookies-from firefox
```

---

## 🍪 Gestión de Cookies Multi-Sitio

Para acceder a videos restringidos por edad, publicaciones privadas autorizadas o contenido exclusivo:

1. **Desde Navegadores**: Usa `--cookies-from <navegador>` (`brave`, `chrome`, `edge`, `firefox`, `opera`).
2. **Archivos de Cookies**:
   - `cookies_[plataforma].txt` (ej. `cookies_instagram.txt`, `cookies_tiktok.txt`, `cookies_twitter.txt`, `cookies_twitch.txt`).
   - `cookies.txt` (archivo general estándar Netscape).
   - `youtube_cookies.txt` (histórico de YouTube).

---

## 📁 Estructura del Proyecto

```
dowloaderVid/
│
├── iniciar.bat                # Menú interactivo principal para Windows (Plug & Play)
├── youtube_downloader.py      # Entrypoint CLI principal
├── media_downloader.py        # Alias entrypoint
├── downloader.py              # Alias entrypoint
├── requirements.txt           # Dependencias de Python
├── README.md                  # Documentación principal del repositorio
├── .gitignore                 # Exclusiones de Git (cookies, descargas, venv)
│
├── docs/                      # Documentación y guías técnicas
│   ├── INICIO_RAPIDO.md       # Guía de inicio rápido y ejemplos
│   ├── INSTALACION.md         # Guía de instalación y configuración
│   ├── ANALISIS_DESCARGA_UNIVERSAL.md # Arquitectura del descargador universal
│   └── ANALISIS_MEJORAS.md    # Análisis técnico de optimizaciones
│
├── scripts/                   # Scripts de configuración e instalación
│   ├── setup.bat              # Script de setup para Windows
│   ├── setup.sh               # Script de setup para Linux/macOS
│   └── instalar_ffmpeg.bat    # Instalador de FFmpeg con winget
│
├── examples/                  # Archivos de ejemplo y plantillas
│   └── urls_ejemplo.txt       # Plantilla para descargas en lote (batch)
│
├── core/                      # Módulos del motor de descarga
│   ├── downloader.py          # UniversalDownloader y descargas concurrentes
│   ├── extractor.py           # UniversalExtractor y selector interactivo
│   └── cookies.py             # Gestión multi-sitio de cookies y sesiones
│
├── ui/                        # Capa de presentación visual
│   ├── console.py             # Rich Console y diagnóstico de errores
│   ├── progress.py            # Hooks de progreso Rich para video, audio y batch
│   └── notifier.py            # Notificaciones nativas Windows Toast
│
├── utils/                     # Utilidades
│   ├── platform_detector.py   # Detección por regex y clasificación
│   ├── clipboard.py           # Portapapeles universal
│   └── formatters.py          # Formateo de bytes, duración y códecs
│
├── tests/                     # Suite de pruebas unitarias
│   ├── test_modular_downloader.py
│   └── test_platform_detector.py
│
└── Descargas/                 # Directorio de salida (ignorado por Git)
    ├── Videos/                # Subcarpetas por plataforma
    ├── Audios/                # Subcarpetas por plataforma
    └── .download_archive.txt  # Historial de descargas
```
