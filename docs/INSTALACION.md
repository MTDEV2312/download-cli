# 📦 Guía de Instalación y Configuración

Guía paso a paso para configurar **Universal Video & Audio Downloader** en Windows, Linux y macOS.

---

## 🚀 Método Rápido (Windows - Recomendado)

1. Haz doble-click en **[iniciar.bat](file:///D:/videos/dowloaderVid/iniciar.bat)**.
2. El sistema detectará automáticamente tu instalación de Python, creará el entorno virtual `venv` e instalará todas las dependencias necesarias de forma automatizada (Plug & Play).

---

## 🛠️ Instalación Manual Paso a Paso

### Paso 1: Clonar o Descargar el Repositorio
Abre tu terminal en la carpeta raíz del proyecto `dowloaderVid`.

### Paso 2: Ejecutar Script de Setup Asistido (Opcional)
* **En Windows**:
  ```cmd
  scripts\setup.bat
  ```
* **En Linux / macOS**:
  ```bash
  bash scripts/setup.sh
  ```

O si prefieres hacerlo manualmente:

### Paso 3: Crear el Entorno Virtual
```bash
# Windows
python -m venv venv

# Linux / macOS
python3 -m venv venv
```

### Paso 4: Activar el Entorno Virtual
* **En Windows (PowerShell)**:
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
  *(Si recibes error de permisos de ejecución en PowerShell, ejecuta: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)*

* **En Windows (CMD)**:
  ```cmd
  venv\Scripts\activate.bat
  ```

* **En Linux / macOS**:
  ```bash
  source venv/bin/activate
  ```

### Paso 5: Instalar Dependencias de Python
Con el entorno virtual activado:
```bash
pip install -r requirements.txt
```

Las dependencias principales son:
* `yt-dlp`: Motor universal de extracción de video y audio (1800+ extractores).
* `yt-dlp-ejs`: Solucionador de desafíos de firma JavaScript de YouTube.
* `rich`: Interfaz moderna con paneles, tablas, colores y barras de progreso multihilo.
* `click`: CLI profesional para gestión de comandos, flags y opciones.
* `mutagen`: Etiquetado ID3, metadatos y carátulas de audio en alta fidelidad.
* `pyperclip`: Detección instantánea de URLs en el portapapeles.
* `winotify`: Notificaciones nativas de Windows Toast.
* `requests`: Peticiones HTTP auxiliares.

---

## ⚡ Dependencias Externas Recomendadas

### 1. FFmpeg (Indispensable para máxima calidad y conversión de audio)
FFmpeg se encarga de combinar pistas separadas de video y audio HD (1080p, 2K, 4K, 8K), remuxear streams HLS/DASH `.m3u8`/`.mpd` y convertir a formatos MP3, FLAC, M4A u OPUS.

* **Windows (winget)**:
  ```powershell
  winget install ffmpeg
  ```
  *O ejecuta el instalador asistido: [scripts/instalar_ffmpeg.bat](file:///D:/videos/dowloaderVid/scripts/instalar_ffmpeg.bat).*
* **Windows (Chocolatey)**:
  ```powershell
  choco install ffmpeg
  ```
* **Linux (Debian/Ubuntu)**:
  ```bash
  sudo apt-get update && sudo apt-get install ffmpeg
  ```
* **macOS (Homebrew)**:
  ```bash
  brew install ffmpeg
  ```

---

## 2. Runtime de JavaScript: Deno o Node.js (Recomendado para YouTube)
YouTube utiliza desafíos de firma dinámica en JavaScript para restringir flujos de alta definición. Al tener **Deno** o **Node.js** en el PATH, `yt-dlp` resuelve estos desafíos automáticamente y descarga a máxima velocidad y resolución.

* **Windows (Recomendado: Deno)**:
  ```powershell
  winget install DenoLand.Deno
  # o Node.js:
  winget install OpenJS.NodeJS
  ```
* **Linux (Debian/Ubuntu)**:
  ```bash
  sudo apt-get install nodejs
  ```
* **macOS (Homebrew)**:
  ```bash
  brew install deno
  # o
  brew install node
  ```

---

## ✅ Verificación de la Instalación

Ejecuta estos comandos en tu terminal para confirmar que todos los componentes están listos:

```bash
# 1. Verificar Python
python --version

# 2. Verificar FFmpeg
ffmpeg -version

# 3. Verificar JS Runtime (Deno o Node)
deno --version
# o
node -v

# 4. Comprobar CLI de Universal Downloader
python youtube_downloader.py --help

# 5. Comprobar diagnóstico multi-plataforma de cookies
python youtube_downloader.py cookies
```

---

## 💡 Uso Rápido

* Para abrir el menú interactivo en Windows: haz doble-click en **[iniciar.bat](file:///D:/videos/dowloaderVid/iniciar.bat)**.
* Para usar la consola CLI: ejecuta `python youtube_downloader.py download [URL] -i`.
