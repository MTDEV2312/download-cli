#!/bin/bash
# Script para configurar el entorno rápidamente en Linux/Mac
# Ejecutar: bash scripts/setup.sh

# Fijar directorio de trabajo a la raíz del proyecto
cd "$(dirname "$0")/.." || exit 1

echo ""
echo "========================================"
echo "  Universal Video & Audio Downloader - Setup"
echo "========================================"
echo ""

# Verificar si Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 no está instalado"
    echo "Instálalo con: sudo apt install python3 (Linux) o brew install python3 (Mac)"
    exit 1
fi

# Verificar si hay un JavaScript runtime (Deno, Node.js o Bun son requeridos por yt-dlp)
if ! command -v deno &> /dev/null && ! command -v node &> /dev/null && ! command -v bun &> /dev/null; then
    echo "[ADVERTENCIA] No se detectó ningún JavaScript runtime (Deno, Node.js o Bun)."
    echo "YouTube requiere un runtime de JS para descargas de alta resolución (1080p+)."
    echo "Se recomienda instalar Deno (curl -fsSL https://deno.land/install.sh | sh) o Node.js."
    echo ""
else
    echo "[OK] Se detectó un JavaScript runtime compatible."
    echo ""
fi

echo "[1/3] Creando entorno virtual..."
python3 -m venv venv

echo "[2/3] Activando entorno virtual..."
source venv/bin/activate

echo "[3/3] Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "  Setup completado exitosamente!"
    echo "========================================"
    echo ""
    echo "Próximos pasos:"
    echo "1. Instalar FFmpeg (requerido para unir audio/video y calidades altas)"
    echo "   Linux: sudo apt-get install ffmpeg"
    echo "   Mac: brew install ffmpeg"
    echo ""
    echo "2. Ejecutar la herramienta:"
    echo "   python youtube_downloader.py --help"
    echo ""
    echo "3. Probar descarga de video:"
    echo "   python youtube_downloader.py download \"URL\""
    echo ""
    echo "Nota: El entorno virtual está activado."
    echo "Para desactivar: deactivate"
    echo "Para reactivar: source venv/bin/activate"
    echo ""
else
    echo "[ERROR] No se pudieron instalar las dependencias"
    exit 1
fi
