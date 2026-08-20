"""
Paquete core del descargador universal de medios (UniversalDownloader).
"""

from core.downloader import (
    UniversalDownloader,
    YouTubeDownloader,
    MediaDownloader,
)
from core.cookies import (
    get_cookie_opts,
    check_cookies_status,
    SUPPORTED_BROWSERS,
)
from core.extractor import (
    get_raw_info,
    get_video_info,
    get_media_info,
    display_info,
    interactive_select_format,
)

__all__ = [
    'UniversalDownloader',
    'YouTubeDownloader',
    'MediaDownloader',
    'get_cookie_opts',
    'check_cookies_status',
    'SUPPORTED_BROWSERS',
    'get_raw_info',
    'get_video_info',
    'get_media_info',
    'display_info',
    'interactive_select_format',
]
