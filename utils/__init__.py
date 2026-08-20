"""
Paquete de utilidades generales para Downloader (formateo, portapapeles y detección de plataformas).
"""

from utils.formatters import (
    format_duration,
    format_bytes,
    format_views,
    format_date,
    clean_codec_name,
    sanitize_filename,
)
from utils.platform_detector import (
    PlatformType,
    PlatformInfo,
    PLATFORM_METADATA,
    PLATFORM_FOLDER_NAMES,
    get_platform_folder_name,
    detect_platform,
    get_platform_info,
    is_valid_url,
    is_valid_media_url,
)
from utils.clipboard import (
    YOUTUBE_REGEX,
    is_youtube_url,
    get_clipboard_url,
    resolve_url,
)

__all__ = [
    'format_duration',
    'format_bytes',
    'format_views',
    'format_date',
    'clean_codec_name',
    'sanitize_filename',
    'PlatformType',
    'PlatformInfo',
    'PLATFORM_METADATA',
    'PLATFORM_FOLDER_NAMES',
    'get_platform_folder_name',
    'detect_platform',
    'get_platform_info',
    'is_valid_url',
    'is_valid_media_url',
    'YOUTUBE_REGEX',
    'is_youtube_url',
    'get_clipboard_url',
    'resolve_url',
]

