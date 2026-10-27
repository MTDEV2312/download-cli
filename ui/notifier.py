"""
Módulo de notificaciones nativas de escritorio para Windows (Windows Toast).
Soporta personalización contextual de iconos y títulos según la plataforma detectada.
"""

import sys
from pathlib import Path
from typing import Optional, Any

from utils.platform_detector import PlatformType, PlatformInfo, get_platform_info

# Intentar importar winotify para notificaciones nativas en Windows
try:
    import winotify
    HAS_WINOTIFY = True
except ImportError:
    HAS_WINOTIFY = False


def get_notification_title(
    platform_info_or_type: Any,
    audio_only: bool = False,
    is_playlist: bool = False,
    is_batch: bool = False
) -> str:
    """
    Genera un título contextual para notificaciones nativas de Windows Toast
    incorporando el icono y nombre legible de la plataforma detectada.

    Ejemplos:
    - 🎵 TikTok Descargado
    - 📸 Instagram Reel Descargado
    - 🐦 Twitter/X Video Descargado
    - ☁️ SoundCloud Audio Descargado
    - 🎬 YouTube Video Descargado
    - 🟣 Twitch VOD Descargado
    - 🎸 Bandcamp Audio Descargado
    - 📡 Stream Directo Descargado
    - 📦 Lote Concurrente Universal Finalizado
    """
    if is_batch:
        return "📦 Lote Concurrente Universal Finalizado"

    if isinstance(platform_info_or_type, PlatformType):
        ptype = platform_info_or_type
        pname = ptype.value.capitalize()
    elif isinstance(platform_info_or_type, PlatformInfo):
        ptype = platform_info_or_type.type
        pname = platform_info_or_type.name
    elif isinstance(platform_info_or_type, str):
        info = get_platform_info(platform_info_or_type)
        ptype = info.type
        pname = info.name
    else:
        ptype = PlatformType.GENERIC
        pname = "Web"

    if is_playlist:
        playlist_titles = {
            PlatformType.YOUTUBE: "📋 YouTube Playlist Completada",
            PlatformType.TIKTOK: "🎵 TikTok Perfil/Lista Completada",
            PlatformType.INSTAGRAM: "📸 Instagram Colección Completada",
            PlatformType.TWITCH: "🟣 Twitch Colección Completada",
            PlatformType.SOUNDCLOUD: "☁️ SoundCloud Set/Álbum Completado",
            PlatformType.BANDCAMP: "🎸 Bandcamp Álbum Completado",
            PlatformType.VIMEO: "🔷 Vimeo Canal/Lista Completada",
            PlatformType.FACEBOOK: "🔵 Facebook Lista Completada",
            PlatformType.KICK: "🟢 Kick Colección/Canal Completado",
        }
        return playlist_titles.get(ptype, f"📋 Lista de {pname} Completada")

    if audio_only or ptype in (PlatformType.SOUNDCLOUD, PlatformType.BANDCAMP):
        audio_titles = {
            PlatformType.YOUTUBE: "🎵 YouTube Audio Guardado",
            PlatformType.TIKTOK: "🎵 TikTok Audio Guardado",
            PlatformType.INSTAGRAM: "📸 Instagram Audio Guardado",
            PlatformType.TWITTER: "🐦 Twitter/X Audio Guardado",
            PlatformType.TWITCH: "🟣 Twitch Audio Guardado",
            PlatformType.SOUNDCLOUD: "☁️ SoundCloud Audio Descargado",
            PlatformType.BANDCAMP: "🎸 Bandcamp Audio Descargado",
            PlatformType.VIMEO: "🔷 Vimeo Audio Guardado",
            PlatformType.FACEBOOK: "🔵 Facebook Audio Guardado",
            PlatformType.REDDIT: "🟠 Reddit Audio Guardado",
            PlatformType.KICK: "🟢 Kick Audio Guardado",
            PlatformType.DIRECT_STREAM: "📡 Stream de Audio Guardado",
            PlatformType.GENERIC: "🎵 Audio Web Guardado",
        }
        return audio_titles.get(ptype, f"🎵 {pname} Audio Guardado")

    video_titles = {
        PlatformType.YOUTUBE: "🎬 YouTube Video Descargado",
        PlatformType.TIKTOK: "🎵 TikTok Descargado",
        PlatformType.INSTAGRAM: "📸 Instagram Reel Descargado",
        PlatformType.TWITTER: "🐦 Twitter/X Video Descargado",
        PlatformType.TWITCH: "🟣 Twitch VOD/Clip Descargado",
        PlatformType.FACEBOOK: "🔵 Facebook Video Descargado",
        PlatformType.REDDIT: "🟠 Reddit Video Descargado",
        PlatformType.VIMEO: "🔷 Vimeo Video Descargado",
        PlatformType.KICK: "🟢 Kick Video Descargado",
        PlatformType.PINTEREST: "📌 Pinterest Video Descargado",
        PlatformType.DIRECT_STREAM: "📡 Stream Directo Descargado",
        PlatformType.GENERIC: "🌐 Video Web Descargado",
    }
    return video_titles.get(ptype, f"🎬 {pname} Video Descargado")


def show_desktop_notification(
    title: str,
    message: str,
    folder_path: Optional[Path] = None,
    icon_path: Optional[str] = None
) -> bool:
    """
    Emite una notificación nativa de Windows Toast al finalizar descargas largas o lotes.
    Si winotify no está disponible o falla, falla silenciosamente sin interrumpir el flujo.
    """
    if not HAS_WINOTIFY or sys.platform != "win32":
        return False

    try:
        app_id = "Universal Media Downloader"
        launch_target = str(folder_path.resolve()) if folder_path and folder_path.exists() else ""

        toast = winotify.Notification(
            app_id=app_id,
            title=title,
            msg=message,
            launch=launch_target
        )

        if icon_path and Path(icon_path).exists():
            toast.set_audio(winotify.audio.Default, loop=False)

        if launch_target:
            toast.add_actions(label="📂 Abrir Carpeta", launch=launch_target)

        toast.show()
        return True
    except Exception:
        return False
