"""
Módulo de interacción con el portapapeles y resolución universal de URLs.
Detecta automáticamente enlaces de cualquier plataforma de video/audio en el portapapeles
y valida URLs multimedia (YouTube, TikTok, Instagram, Twitter/X, Twitch, SoundCloud, streams directos, etc.).
"""

import re
from typing import Optional, Any
import pyperclip
from rich.panel import Panel
from rich.prompt import Prompt

from utils.platform_detector import (
    PlatformType,
    PlatformInfo,
    detect_platform,
    get_platform_info,
    is_valid_url,
    is_valid_media_url,
)

# Expresión regular histórica para YouTube (mantenida por compatibilidad regresiva)
YOUTUBE_REGEX = re.compile(
    r'(https?://)?((www|m|music)\.)?(youtube\.com/(watch\?[^\s"\'<>]+|playlist\?[^\s"\'<>]+|shorts/[^\s"\'<>]+|live/[^\s"\'<>]+)|youtu\.be/[^\s"\'<>]+)',
    re.IGNORECASE
)

# Expresión regular para extraer URLs contenidas dentro de un bloque de texto
EMBEDDED_URL_REGEX = re.compile(
    r'https?://[^\s"\'<>]+|(?:[a-zA-Z0-9_\-]+\.)+(?:com|org|net|tv|fm|io|co|me|be|app|cc|gl|is|so|to|ly|video|stream|audio|edu|gov)(?::\d+)?/[^\s"\'<>]*',
    re.IGNORECASE
)


def is_youtube_url(url: Optional[str]) -> bool:
    """
    Valida si una cadena contiene una URL válida de YouTube.
    Mantenida como función de conveniencia y compatibilidad regresiva.
    """
    if not url or not isinstance(url, str):
        return False
    return bool(YOUTUBE_REGEX.search(url.strip()))


def get_clipboard_url() -> Optional[str]:
    """
    Lee el portapapeles del sistema y extrae cualquier URL válida de medios si está presente
    (YouTube, TikTok, Instagram, Twitter/X, Twitch, SoundCloud, streams directos, etc.).
    Retorna la URL limpia con esquema https:// o None si no hay ninguna.
    """
    try:
        text = pyperclip.paste()
        if not text:
            return None
        
        text_clean = text.strip()

        # 1. Si el texto completo es una URL válida directa
        if is_valid_url(text_clean):
            if not text_clean.startswith(('http://', 'https://')):
                text_clean = 'https://' + text_clean
            return text_clean

        # 2. Buscar si hay una URL contenida dentro de texto pegado
        match = EMBEDDED_URL_REGEX.search(text_clean)
        if match:
            extracted = match.group(0).strip()
            if is_valid_url(extracted):
                if not extracted.startswith(('http://', 'https://')):
                    extracted = 'https://' + extracted
                return extracted

    except Exception:
        pass

    return None


def resolve_url(
    url: Optional[str] = None,
    prompt_message: str = "Introduce la URL de descarga",
    allow_clipboard: bool = True,
    console_instance: Optional[Any] = None
) -> str:
    """
    Obtiene la URL a procesar. Si no se especificó como argumento,
    detecta automáticamente si hay una URL en el portapapeles y la ofrece como sugerencia,
    mostrando el badge estilizado de la plataforma identificada.
    """
    if url and is_valid_url(url):
        return url.strip()

    clipboard_url = get_clipboard_url() if allow_clipboard else None

    if clipboard_url:
        _, platform_name, badge = detect_platform(clipboard_url)
        if console_instance:
            console_instance.print(Panel(
                f"[bold cyan]📋 URL detectada en el portapapeles:[/bold cyan] {badge}\n"
                f"[bold underline yellow]{clipboard_url}[/bold underline yellow]\n\n"
                f"[dim]Presiona Enter para usarla, o pega otra URL a continuación.[/dim]",
                title="[bold cyan]Portapapeles[/bold cyan]",
                border_style="cyan",
                expand=False
            ))
        entered = Prompt.ask(
            f"[bold green]?[/bold green] {prompt_message}",
            default=clipboard_url,
            console=console_instance
        )
        return entered.strip()
    else:
        entered = Prompt.ask(
            f"[bold green]?[/bold green] {prompt_message}",
            console=console_instance
        )
        return entered.strip()
