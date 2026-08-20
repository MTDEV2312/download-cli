"""
Módulo de formateo y utilidades para strings, bytes, duraciones y nombres de archivos.
"""

from typing import Optional


def format_duration(seconds: Optional[int]) -> str:
    """Convierte segundos a formato legible (ej. 1h 23m 45s o 3m 20s)"""
    if not seconds:
        return "Desconocida"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{int(hours)}h {int(minutes):02d}m {int(secs):02d}s"
    return f"{int(minutes)}m {int(secs):02d}s"


def format_bytes(size: Optional[int]) -> str:
    """Convierte bytes a formato legible (KB, MB, GB)"""
    if not size or size <= 0:
        return "N/A"
    if size >= 1024 * 1024 * 1024:
        return f"{size / (1024**3):.2f} GB"
    if size >= 1024 * 1024:
        return f"{size / (1024**2):.1f} MB"
    return f"{size / 1024:.1f} KB"


def format_views(count: Optional[int]) -> str:
    """Convierte número de vistas a formato amigable (ej. 1.2M, 450K)"""
    if count is None:
        return "N/A"
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M vistas"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K vistas"
    return f"{count:,} vistas"


def format_date(date_str: Optional[str]) -> str:
    """Formatea fecha YYYYMMDD a YYYY-MM-DD"""
    if not date_str or len(str(date_str)) != 8:
        return str(date_str) if date_str else "N/A"
    s = str(date_str)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def clean_codec_name(codec: Optional[str]) -> str:
    """Traduce identificadores técnicos de códecs a nombres claros"""
    if not codec or codec == "none":
        return "-"
    c = codec.lower()
    if c.startswith("avc1") or c.startswith("h264"):
        return "H.264 (AVC)"
    if c.startswith("vp09") or c.startswith("vp9"):
        return "VP9"
    if c.startswith("av01") or c.startswith("av1"):
        return "AV1"
    if c.startswith("mp4a"):
        return "AAC"
    if "opus" in c:
        return "Opus"
    if "mp3" in c:
        return "MP3"
    if "flac" in c:
        return "FLAC"
    return codec.split(".")[0]


def sanitize_filename(filename: str) -> str:
    """Sanitiza el nombre de archivo/carpeta removiendo caracteres inválidos en Windows"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    
    filename = filename.encode('ascii', 'ignore').decode('ascii')
    filename = ' '.join(filename.split())
    
    if len(filename) > 200:
        filename = filename[:200]
    
    if not filename.strip():
        filename = "Video"
    
    return filename.strip()
