"""
Paquete de componentes de interfaz de usuario con Rich y notificaciones.
"""

from ui.console import (
    console,
    print_banner,
    print_success,
    print_error,
    print_warning,
    print_info_panel,
    handle_download_error,
    prompt_interactive_recovery,
)
from ui.notifier import (
    HAS_WINOTIFY,
    show_desktop_notification,
    get_notification_title,
)
from ui.progress import (
    YtDlpQuietLogger,
    RichDownloadProgress,
    RichPlaylistProgress,
    RichConcurrentBatchProgress,
    classify_stream_label,
    clean_stream_title,
    get_postprocessor_label,
)

__all__ = [
    'console',
    'print_banner',
    'print_success',
    'print_error',
    'print_warning',
    'print_info_panel',
    'handle_download_error',
    'prompt_interactive_recovery',
    'HAS_WINOTIFY',
    'show_desktop_notification',
    'get_notification_title',
    'YtDlpQuietLogger',
    'RichDownloadProgress',
    'RichPlaylistProgress',
    'RichConcurrentBatchProgress',
    'classify_stream_label',
    'clean_stream_title',
    'get_postprocessor_label',
]
