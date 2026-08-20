# 🚀 GUÍA DE INICIO RÁPIDO

Bienvenido a **Universal Video & Audio Downloader**. Esta herramienta te permite descargar videos y audios de **YouTube, TikTok, Instagram, Twitter/X, Twitch, SoundCloud, Bandcamp, Vimeo, Facebook, Reddit, Kick**, streams directos **HLS (`.m3u8`) / DASH (`.mpd`)** y más de **1800+ sitios web**.

---

## ⚡ Inicio Rápido en Windows (La opción más fácil)

1. **Abre el Menú Interactivo**:
   - Haz doble-click en **[iniciar.bat](file:///D:/videos/dowloaderVid/iniciar.bat)**.
   - Si es la primera vez, el sistema creará automáticamente el entorno virtual e instalará las librerías necesarias (Plug & Play).

2. **Copia cualquier enlace y pulsa Enter**:
   - Copia el enlace de un video de TikTok, reel de Instagram, video de YouTube, tweet o canción de SoundCloud.
   - En el menú interactivo, selecciona la opción deseada (ej. `1` para Video, `2` para Audio, `3` para Selector Interactivo) y presiona Enter sin escribir nada: la herramienta tomará automáticamente la URL de tu portapapeles.

---

## 💻 Para Linux y macOS

1. **Instalar dependencias y activar entorno**:
   ```bash
   bash scripts/setup.sh
   source venv/bin/activate
   ```

2. **Ejecutar descarga**:
   ```bash
   python youtube_downloader.py download "URL"
   ```

---

## 📋 Opciones del Menú Interactivo (`iniciar.bat`)

* **1. Descargar Video Universal**: Descarga en máxima calidad (4K/1080p/720p) de cualquier red social o sitio web.
* **2. Descargar Audio de Alta Fidelidad**: Extrae audio en MP3 (320k, 256k, 192k), FLAC (Lossless sin pérdida), M4A (AAC), OPUS o WAV con carátula y metadatos.
* **3. Selector Interactivo de Formatos y Resoluciones (-i)**: Muestra una tabla con todas las resoluciones, tasas de cuadros (fps) y tamaños reales antes de descargar.
* **4. Descargar Lista de Reproducción, Perfil o Álbum**: Descarga playlists de YouTube, sets de SoundCloud, álbumes de Bandcamp o perfiles de TikTok.
* **5. Descarga en Lote Concurrente desde Archivo TXT (Batch)**: Descarga múltiples enlaces en paralelo con control de concurrencia y pausas anti-bloqueo.
* **6. Ver Información y Formatos de una URL (Info)**: Muestra metadatos y tabla técnica de streams disponibles.
* **7. Diagnóstico de Cookies y Sesiones de Navegadores**: Audita sesiones activas en Chrome, Brave, Firefox, Edge u Opera para contenido privado/restringido.
* **8. Instalar / Verificar FFmpeg**: Comprueba el estado de FFmpeg y permite instalarlo vía winget.
* **9. Actualizar yt-dlp y Dependencias**: Mantiene el motor de extracción al día con las últimas plataformas.
* **0. Salir**.

---

## 🎯 Ejemplos Rápidos por Plataforma (CLI)

### 🎵 TikTok (Sin marca de agua)
```bash
python youtube_downloader.py download "https://www.tiktok.com/@usuario/video/123456789"
```

### 📸 Instagram (Reels y Posts)
```bash
python youtube_downloader.py download "https://www.instagram.com/reel/C123456789/" --organize-by-platform
```

### 🐦 Twitter / X
```bash
python youtube_downloader.py download "https://x.com/usuario/status/123456789"
```

### ☁️ SoundCloud (Audio MP3 320k o Álbumes)
```bash
python youtube_downloader.py download "https://soundcloud.com/artista/pista" --audio --audio-format mp3
python youtube_downloader.py playlist "https://soundcloud.com/artista/sets/album" --audio
```

### 🎸 Bandcamp (Audio FLAC sin pérdida)
```bash
python youtube_downloader.py download "https://artista.bandcamp.com/track/cancion" --audio --audio-format flac
```

### 🟣 Twitch (VODs y Clips)
```bash
python youtube_downloader.py download "https://www.twitch.tv/videos/123456789" -i
```

### 📡 Streams Directos HLS / DASH
```bash
python youtube_downloader.py download "https://servidor.com/live/stream.m3u8"
```

### 📦 Descarga Masiva en Paralelo
```bash
python youtube_downloader.py batch examples/urls_ejemplo.txt --concurrency 3 --delay 1.0 --organize-by-platform
```

---

## 🍪 Configuración y Organización de Cookies

Para contenido restringido, privado o con verificación anti-bot:

1. **Ubicación de archivos**: Guarda tus archivos Netscape `.txt` en la carpeta `cookies/` de la raíz del proyecto.
   - `cookies/cookies.txt` — Universal
   - `cookies/cookies_youtube.txt` — YouTube (edad 18+, miembros)
   - `cookies/cookies_instagram.txt` — Instagram (Stories, reels privados)
   - `cookies/cookies_tiktok.txt` — TikTok
   - `cookies/cookies_twitter.txt` — Twitter / X
   - `cookies/cookies_twitch.txt` — Twitch (sub-only)
   - `cookies/cookies_facebook.txt` — Facebook

2. **Seguridad**: La carpeta `cookies/` está ignorada en `.gitignore` para garantizar que tus credenciales nunca se suban a Git.

3. **Diagnóstico**:
   ```bash
   python youtube_downloader.py cookies
   ```

