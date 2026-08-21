"""
Paquete core del descargador universal de medios (UniversalDownloader).
"""

from core.downloader import (
    UniversalDownloader,
    YouTubeDownloader,
    MediaDownloader,
    calculate_pacing_delay,
)
from core.cookies import (
    get_cookie_opts,
    check_cookies_status,
    parse_browser_spec,
    get_available_browser_profiles,
    extract_cookies_lock_safe,
    SUPPORTED_BROWSERS,
)
from core.extractor import (
    get_raw_info,
    get_video_info,
    get_media_info,
    display_info,
    interactive_select_format,
    FALLBACK_PLAYER_CLIENTS,
    extract_info_with_client_fallback,
)

__all__ = [
    'UniversalDownloader',
    'YouTubeDownloader',
    'MediaDownloader',
    'calculate_pacing_delay',
    'get_cookie_opts',
    'check_cookies_status',
    'parse_browser_spec',
    'get_available_browser_profiles',
    'extract_cookies_lock_safe',
    'SUPPORTED_BROWSERS',
    'get_raw_info',
    'get_video_info',
    'get_media_info',
    'display_info',
    'interactive_select_format',
    'FALLBACK_PLAYER_CLIENTS',
    'extract_info_with_client_fallback',
]
