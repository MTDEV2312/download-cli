"""
Módulo de Detección Dinámica de Plataformas y Validación de URLs Multimedia.
Identifica la red social, plataforma de video/audio o stream directo a partir de una URL,
asociando iconos, badges para Rich Console y metadatos específicos.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, List, Pattern
from urllib.parse import urlparse


class PlatformType(Enum):
    """Enumeración de plataformas y tipos de medios soportados"""
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    TWITCH = "twitch"
    FACEBOOK = "facebook"
    REDDIT = "reddit"
    SOUNDCLOUD = "soundcloud"
    BANDCAMP = "bandcamp"
    VIMEO = "vimeo"
    KICK = "kick"
    PINTEREST = "pinterest"
    DIRECT_STREAM = "direct_stream"
    GENERIC = "generic"


@dataclass
class PlatformInfo:
    """Metadatos asociados a una plataforma detectada"""
    type: PlatformType
    name: str
    icon: str
    color: str
    badge_rich: str
    supports_playlists: bool = False
    recommended_audio_fmt: str = "mp3"


# Metadatos predefinidos por cada plataforma
PLATFORM_METADATA: dict[PlatformType, PlatformInfo] = {
    PlatformType.YOUTUBE: PlatformInfo(
        type=PlatformType.YOUTUBE,
        name="YouTube",
        icon="🔴",
        color="red",
        badge_rich="[bold white on #ff0000] 🔴 YouTube [/]",
        supports_playlists=True,
        recommended_audio_fmt="mp3"
    ),
    PlatformType.TIKTOK: PlatformInfo(
        type=PlatformType.TIKTOK,
        name="TikTok",
        icon="🎵",
        color="cyan",
        badge_rich="[bold black on #00f2fe] 🎵 TikTok [/]",
        supports_playlists=True,
        recommended_audio_fmt="mp3"
    ),
    PlatformType.INSTAGRAM: PlatformInfo(
        type=PlatformType.INSTAGRAM,
        name="Instagram",
        icon="📸",
        color="magenta",
        badge_rich="[bold white on #e1306c] 📸 Instagram [/]",
        supports_playlists=True,
        recommended_audio_fmt="m4a"
    ),
    PlatformType.TWITTER: PlatformInfo(
        type=PlatformType.TWITTER,
        name="Twitter / X",
        icon="🐦",
        color="blue",
        badge_rich="[bold white on #1da1f2] 🐦 Twitter / X [/]",
        supports_playlists=False,
        recommended_audio_fmt="mp3"
    ),
    PlatformType.TWITCH: PlatformInfo(
        type=PlatformType.TWITCH,
        name="Twitch",
        icon="🟣",
        color="purple",
        badge_rich="[bold white on #9146ff] 🟣 Twitch [/]",
        supports_playlists=True,
        recommended_audio_fmt="mp3"
    ),
    PlatformType.FACEBOOK: PlatformInfo(
        type=PlatformType.FACEBOOK,
        name="Facebook",
        icon="🔵",
        color="blue",
        badge_rich="[bold white on #1877f2] 🔵 Facebook [/]",
        supports_playlists=True,
        recommended_audio_fmt="mp3"
    ),
    PlatformType.REDDIT: PlatformInfo(
        type=PlatformType.REDDIT,
        name="Reddit",
        icon="🟠",
        color="bright_red",
        badge_rich="[bold white on #ff4500] 🟠 Reddit [/]",
        supports_playlists=False,
        recommended_audio_fmt="mp3"
    ),
    PlatformType.SOUNDCLOUD: PlatformInfo(
        type=PlatformType.SOUNDCLOUD,
        name="SoundCloud",
        icon="☁️",
        color="bright_yellow",
        badge_rich="[bold white on #ff5500] ☁️ SoundCloud [/]",
        supports_playlists=True,
        recommended_audio_fmt="mp3"
    ),
    PlatformType.BANDCAMP: PlatformInfo(
        type=PlatformType.BANDCAMP,
        name="Bandcamp",
        icon="🎸",
        color="cyan",
        badge_rich="[bold white on #629aa9] 🎸 Bandcamp [/]",
        supports_playlists=True,
        recommended_audio_fmt="flac"
    ),
    PlatformType.VIMEO: PlatformInfo(
        type=PlatformType.VIMEO,
        name="Vimeo",
        icon="🔷",
        color="bright_blue",
        badge_rich="[bold white on #1ab7ea] 🔷 Vimeo [/]",
        supports_playlists=True,
        recommended_audio_fmt="mp3"
    ),
    PlatformType.KICK: PlatformInfo(
        type=PlatformType.KICK,
        name="Kick",
        icon="🟢",
        color="green",
        badge_rich="[bold black on #53fc18] 🟢 Kick [/]",
        supports_playlists=True,
        recommended_audio_fmt="mp3"
    ),
    PlatformType.PINTEREST: PlatformInfo(
        type=PlatformType.PINTEREST,
        name="Pinterest",
        icon="📌",
        color="red",
        badge_rich="[bold white on #e60023] 📌 Pinterest [/]",
        supports_playlists=False,
        recommended_audio_fmt="mp3"
    ),
    PlatformType.DIRECT_STREAM: PlatformInfo(
        type=PlatformType.DIRECT_STREAM,
        name="Stream Directo",
        icon="📡",
        color="green",
        badge_rich="[bold white on #00a86b] 📡 Stream Directo [/]",
        supports_playlists=False,
        recommended_audio_fmt="mp3"
    ),
    PlatformType.GENERIC: PlatformInfo(
        type=PlatformType.GENERIC,
        name="Web Genérica",
        icon="🌐",
        color="white",
        badge_rich="[bold white on #4a5568] 🌐 Web Genérica [/]",
        supports_playlists=False,
        recommended_audio_fmt="mp3"
    ),
}


# Patrones de expresiones regulares ordenados por especificidad (con delimitadores de dominio)
PLATFORM_PATTERNS: List[Tuple[Pattern, PlatformType]] = [
    (re.compile(r'(?:^|[\./])(?:youtube\.com|youtu\.be)(?:[:/]|$)', re.IGNORECASE), PlatformType.YOUTUBE),
    (re.compile(r'(?:^|[\./])(?:tiktok\.com)(?:[:/]|$)', re.IGNORECASE), PlatformType.TIKTOK),
    (re.compile(r'(?:^|[\./])(?:instagram\.com|instagr\.am)(?:[:/]|$)', re.IGNORECASE), PlatformType.INSTAGRAM),
    (re.compile(r'(?:^|[\./])(?:twitter\.com|x\.com|t\.co)(?:[:/]|$)', re.IGNORECASE), PlatformType.TWITTER),
    (re.compile(r'(?:^|[\./])(?:twitch\.tv)(?:[:/]|$)', re.IGNORECASE), PlatformType.TWITCH),
    (re.compile(r'(?:^|[\./])(?:facebook\.com|fb\.watch|fb\.com)(?:[:/]|$)', re.IGNORECASE), PlatformType.FACEBOOK),
    (re.compile(r'(?:^|[\./])(?:reddit\.com|v\.redd\.it|redd\.it)(?:[:/]|$)', re.IGNORECASE), PlatformType.REDDIT),
    (re.compile(r'(?:^|[\./])(?:soundcloud\.com)(?:[:/]|$)', re.IGNORECASE), PlatformType.SOUNDCLOUD),
    (re.compile(r'(?:^|[\./])(?:bandcamp\.com)(?:[:/]|$)', re.IGNORECASE), PlatformType.BANDCAMP),
    (re.compile(r'(?:^|[\./])(?:vimeo\.com)(?:[:/]|$)', re.IGNORECASE), PlatformType.VIMEO),
    (re.compile(r'(?:^|[\./])(?:kick\.com)(?:[:/]|$)', re.IGNORECASE), PlatformType.KICK),
    (re.compile(r'(?:^|[\./])(?:pinterest\.com|pin\.it)(?:[:/]|$)', re.IGNORECASE), PlatformType.PINTEREST),
]

# Extensiones de archivos y manifiestos de stream directos
DIRECT_STREAM_PATTERN = re.compile(
    r'\.(m3u8|mpd|mp4|webm|m4a|mp3|ogg|opus|flac|wav|ts|mov|mkv)(?:$|[?#])',
    re.IGNORECASE
)

# Regex general de URL HTTP/HTTPS
URL_STRUCTURE_REGEX = re.compile(
    r'^(https?://)?(?:[a-zA-Z0-9_\-]+\.)+[a-zA-Z]{2,}(?::\d+)?(?:/.*)?$',
    re.IGNORECASE
)


def is_valid_url(url: Optional[str]) -> bool:
    """
    Validador universal de URLs.
    Comprueba si una cadena es una URL HTTP/HTTPS bien formateada o un enlace de stream válido.
    Acepta URLs con o sin esquema 'http(s)://' siempre que tengan un dominio y estructura válida.
    """
    if not url or not isinstance(url, str):
        return False
    
    url_str = url.strip()
    if not url_str or len(url_str) < 4:
        return False
    
    # Comprobar si contiene espacios internos (inválido para URL)
    if any(c in url_str for c in (' ', '\t', '\n', '\r', '"', "'", '<', '>')):
        return False

    # Si no tiene esquema, añadir temporalmente https:// para validar con urlparse
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', url_str):
        url_eval = "https://" + url_str
    else:
        url_eval = url_str

    try:
        parsed = urlparse(url_eval)
        if parsed.scheme not in ('http', 'https'):
            return False
        
        netloc = parsed.netloc.lower()
        if not netloc:
            return False

        # Permitir localhost o IPs locales para entornos de prueba/desarrollo
        host = netloc.split(':')[0]
        if host in ('localhost', '127.0.0.1'):
            return True

        # Debe tener al menos dos partes no vacías en el dominio (ej. example.com)
        parts = host.split('.')
        if len(parts) < 2 or any(len(p) == 0 for p in parts):
            return False

        # El TLD debe ser alfabético y de al menos 2 caracteres
        tld = parts[-1]
        if not tld.isalpha() or len(tld) < 2:
            return False

        return True
    except Exception:
        return False


# Alias de conveniencia
is_valid_media_url = is_valid_url


def get_platform_info(url: Optional[str]) -> PlatformInfo:
    """
    Identifica la plataforma de una URL y retorna su objeto PlatformInfo con metadatos.
    Si la URL no coincide con una plataforma específica o es genérica, retorna PlatformType.GENERIC.
    """
    if not url or not isinstance(url, str) or not is_valid_url(url):
        return PLATFORM_METADATA[PlatformType.GENERIC]

    url_str = url.strip()

    # 1. Comprobar patrones de plataformas específicas
    for pattern, platform_type in PLATFORM_PATTERNS:
        if pattern.search(url_str):
            return PLATFORM_METADATA[platform_type]

    # 2. Comprobar si es un stream directo (m3u8, mpd, mp4, etc.)
    if DIRECT_STREAM_PATTERN.search(url_str):
        return PLATFORM_METADATA[PlatformType.DIRECT_STREAM]

    # 3. Fallback: URL web genérica soportada por yt-dlp
    return PLATFORM_METADATA[PlatformType.GENERIC]


def detect_platform(url: Optional[str]) -> Tuple[PlatformType, str, str]:
    """
    Detecta la plataforma a partir de una URL.
    Retorna una tupla de 3 elementos:
    (PlatformType, Nombre_Legible, Badge_Rich)
    
    Ejemplo:
        (PlatformType.TIKTOK, "TikTok", "[bold black on #00f2fe] 🎵 TikTok [/]")
    """
    info = get_platform_info(url)
    return info.type, info.name, info.badge_rich


# Mapeo de nombres canónicos limpios de subcarpetas por plataforma
PLATFORM_FOLDER_NAMES: dict[PlatformType, str] = {
    PlatformType.YOUTUBE: "YouTube",
    PlatformType.TIKTOK: "TikTok",
    PlatformType.INSTAGRAM: "Instagram",
    PlatformType.TWITTER: "Twitter",
    PlatformType.TWITCH: "Twitch",
    PlatformType.FACEBOOK: "Facebook",
    PlatformType.REDDIT: "Reddit",
    PlatformType.SOUNDCLOUD: "SoundCloud",
    PlatformType.BANDCAMP: "Bandcamp",
    PlatformType.VIMEO: "Vimeo",
    PlatformType.KICK: "Kick",
    PlatformType.PINTEREST: "Pinterest",
    PlatformType.DIRECT_STREAM: "Otros",
    PlatformType.GENERIC: "Otros",
}


def get_platform_folder_name(platform: Optional[PlatformType]) -> str:
    """
    Retorna el nombre canónico de la subcarpeta para la plataforma dada.
    Retorna "Otros" si es None, GENERIC, DIRECT_STREAM o cualquier plataforma no mapeada.
    """
    if platform is None:
        return "Otros"
    return PLATFORM_FOLDER_NAMES.get(platform, "Otros")

