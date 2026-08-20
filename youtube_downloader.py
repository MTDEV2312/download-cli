#!/usr/bin/env python3
"""
Universal & YouTube Video/Audio Downloader CLI
Descarga videos y audios de YouTube, TikTok, Instagram, Twitter/X, Twitch, SoundCloud,
Bandcamp, Vimeo, Kick, streams directos HLS/DASH y más de 1800 sitios soportados por yt-dlp.
Interfaz moderna con Rich, portapapeles universal y notificaciones nativas Windows Toast.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# Asegurar encoding UTF-8 en Windows para emojis y caracteres especiales
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import click
from rich.panel import Panel

from core.downloader import (
    UniversalDownloader,
    YouTubeDownloader,
    MediaDownloader,
)
from core.extractor import (
    get_raw_info,
    get_video_info,
    get_media_info,
    display_info,
    interactive_select_format,
)
from core.cookies import (
    get_cookie_opts,
    check_cookies_status,
    SUPPORTED_BROWSERS,
)
from ui.console import (
    console,
    print_banner,
    print_success,
    print_error,
    print_warning,
    print_info_panel,
    handle_download_error,
)
from ui.notifier import show_desktop_notification, HAS_WINOTIFY
from ui.progress import (
    YtDlpQuietLogger,
    RichDownloadProgress,
    RichPlaylistProgress,
    RichConcurrentBatchProgress,
)
from utils.formatters import (
    format_duration,
    format_bytes,
    format_views,
    format_date,
    clean_codec_name,
    sanitize_filename,
)
from utils.clipboard import (
    YOUTUBE_REGEX,
    is_youtube_url,
    get_clipboard_url,
    resolve_url,
)
from utils.platform_detector import (
    PlatformType,
    PlatformInfo,
    PLATFORM_METADATA,
    detect_platform,
    get_platform_info,
    is_valid_url,
    is_valid_media_url,
)


# ==============================================================================
# Click CLI Interface
# ==============================================================================

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """🌐 Universal Video & Audio Downloader - Descarga medios de 1800+ plataformas en alta calidad con interfaz Rich"""
    if ctx.invoked_subcommand is None:
        print_banner()
        console.print("[cyan]Usa [bold white]--help[/bold white] para ver los comandos disponibles.[/cyan]\n")
        console.print("[dim]Ejemplos rápidos:[/dim]")
        console.print("  • [green]python youtube_downloader.py download[/green]                                (detecta URL del portapapeles)")
        console.print("  • [green]python youtube_downloader.py download \"URL\" -i[/green]                           (selector interactivo de calidades)")
        console.print("  • [green]python youtube_downloader.py download \"URL\" --organize-by-platform[/green]        (organiza en subcarpetas por plataforma)")
        console.print("  • [green]python youtube_downloader.py download \"URL\" --audio --audio-format mp3[/green]     (descargar solo audio)")
        console.print("  • [green]python youtube_downloader.py download \"URL\" --subtitles[/green]                  (con subtítulos)")
        console.print("  • [green]python youtube_downloader.py info \"URL\"[/green]                                    (ver resoluciones y formatos)")
        console.print("  • [green]python youtube_downloader.py cookies[/green]                                       (diagnosticar cookies multi-sitio)")
        console.print("  • [green]python youtube_downloader.py playlist \"URL\"[/green]                                 (descargar playlist o álbum)")
        console.print("  • [green]python youtube_downloader.py batch urls.txt --concurrency 3[/green]                (descarga en lote concurrente)\n")


@cli.command()
@click.argument('url', required=False)
@click.option('--quality', '-q', default='1080', 
              type=click.Choice(['720', '1080', '1440', '2160', 'best']),
              help='Calidad de video deseada (default: 1080)')
@click.option('--audio', '-a', is_flag=True,
              help='Descargar solo audio')
@click.option('--audio-format', '-af', default='mp3',
              type=click.Choice(['mp3', 'flac', 'm4a', 'opus', 'wav']),
              help='Formato de audio deseado (default: mp3)')
@click.option('--audio-quality', '-aq', default='320',
              type=click.Choice(['320', '256', '192', '128']),
              help='Bitrate de audio en kbps (default: 320)')
@click.option('--embed-thumbnail/--no-thumbnail', default=True,
              help='Incrustar carátula/miniatura en el archivo de audio')
@click.option('--interactive-format', '-i', is_flag=True,
              help='Abrir selector interactivo de resoluciones y formatos reales antes de descargar')
@click.option('--subtitles/--no-subtitles', default=False,
              help='Descargar subtítulos del video')
@click.option('--sub-lang', default='es,en,es-419',
              help='Idiomas de subtítulos deseados (default: es,en,es-419)')
@click.option('--embed-subs/--no-embed-subs', default=True,
              help='Incrustar subtítulos en el contenedor del video')
@click.option('--write-subs/--no-write-subs', default=False,
              help='Guardar archivos de subtítulos (.srt / .vtt) en disco')
@click.option('--cookies-from', type=click.Choice(SUPPORTED_BROWSERS),
              help='Extraer cookies directamente del navegador especificado')
@click.option('--cookies-file', type=click.Path(exists=True),
              help='Ruta al archivo de cookies (ej. cookies.txt, cookies_instagram.txt, youtube_cookies.txt)')
@click.option('--notify/--no-notify', default=True,
              help='Mostrar notificación nativa de Windows Toast al finalizar')
@click.option('--archive/--no-archive', default=True,
              help='Usar archivo de historial para evitar re-descargas')
@click.option('--organize-by-platform/--no-organize-by-platform', default=True,
              help='Organizar descargas en subcarpetas por plataforma (ej. Descargas/Videos/TikTok/) (default: True)')
@click.option('--output', '-o', default='Descargas',
              help='Carpeta de salida (default: Descargas)')
@click.option('--clipboard', '-c', is_flag=True,
              help='Usar automáticamente la URL del portapapeles sin solicitar confirmación')
def download(
    url, quality, audio, audio_format, audio_quality, embed_thumbnail,
    interactive_format, subtitles, sub_lang, embed_subs, write_subs,
    cookies_from, cookies_file, notify, archive, organize_by_platform, output, clipboard
):
    """
    Descarga un video o audio de cualquier plataforma soportada (YouTube, TikTok, Instagram, Twitter/X, Twitch, SoundCloud, Bandcamp, Vimeo, HLS/DASH streams, etc.).
    Si no se pasa URL, detecta automáticamente si hay una en el portapapeles.
    """
    if clipboard:
        clip_url = get_clipboard_url()
        if clip_url:
            url = clip_url
        else:
            print_error("Portapapeles sin URL", "No se detectó ninguna URL multimedia en el portapapeles.")
            sys.exit(1)
    else:
        url = resolve_url(url, "Introduce la URL del video o medio a descargar")

    if not url:
        print_error("Operación cancelada", "No se ingresó ninguna URL.")
        sys.exit(1)

    downloader = UniversalDownloader(output, use_archive=archive, organize_by_platform=organize_by_platform)

    info_dict = None
    if interactive_format:
        selection = interactive_select_format(url, downloader, cookies_from=cookies_from, cookies_file=cookies_file)
        if not selection:
            sys.exit(0)
        quality = selection['quality']
        audio = selection['audio_only']
        audio_format = selection['audio_format']
        audio_quality = selection['audio_quality']
        subtitles = selection['subtitles']
        sub_lang = selection['sub_lang']
        embed_subs = selection['embed_subs']
        write_subs = selection['write_subs']
        info_dict = selection.get('info_dict')

    success = downloader.download_video(
        url,
        quality=quality,
        audio_only=audio,
        audio_format=audio_format,
        audio_quality=audio_quality,
        embed_thumbnail=embed_thumbnail,
        subtitles=subtitles,
        sub_lang=sub_lang,
        embed_subs=embed_subs,
        write_subs=write_subs,
        cookies_from=cookies_from,
        cookies_file=cookies_file,
        use_archive=archive,
        info_dict=info_dict,
        notify=notify,
        organize_by_platform=organize_by_platform
    )
    sys.exit(0 if success else 1)


@cli.command()
@click.argument('url', required=False)
@click.option('--cookies-from', type=click.Choice(SUPPORTED_BROWSERS),
              help='Extraer cookies del navegador')
@click.option('--cookies-file', type=click.Path(exists=True),
              help='Ruta al archivo de cookies')
@click.option('--clipboard', '-c', is_flag=True,
              help='Usar automáticamente la URL del portapapeles')
def info(url, cookies_from, cookies_file, clipboard):
    """
    Muestra metadatos y tabla visual con todos los streams, formatos y subtítulos disponibles.
    """
    if clipboard:
        clip_url = get_clipboard_url()
        if clip_url:
            url = clip_url
        else:
            print_error("Portapapeles sin URL", "No se detectó ninguna URL multimedia en el portapapeles.")
            sys.exit(1)
    else:
        url = resolve_url(url, "Introduce la URL del medio a consultar")

    if not url:
        print_error("Operación cancelada", "No se ingresó ninguna URL.")
        sys.exit(1)

    downloader = UniversalDownloader()
    downloader.display_info(url, cookies_from=cookies_from, cookies_file=cookies_file)


@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('--quality', '-q', default='1080',
              type=click.Choice(['720', '1080', '1440', '2160', 'best']),
              help='Calidad de descarga')
@click.option('--audio', '-a', is_flag=True,
              help='Descargar solo audio')
@click.option('--audio-format', '-af', default='mp3',
              type=click.Choice(['mp3', 'flac', 'm4a', 'opus', 'wav']),
              help='Formato de audio deseado (default: mp3)')
@click.option('--audio-quality', '-aq', default='320',
              type=click.Choice(['320', '256', '192', '128']),
              help='Bitrate de audio en kbps (default: 320)')
@click.option('--embed-thumbnail/--no-thumbnail', default=True,
              help='Incrustar carátula/miniatura en el archivo de audio')
@click.option('--subtitles/--no-subtitles', default=False,
              help='Descargar subtítulos')
@click.option('--sub-lang', default='es,en,es-419',
              help='Idiomas de subtítulos (default: es,en,es-419)')
@click.option('--embed-subs/--no-embed-subs', default=True,
              help='Incrustar subtítulos en el video')
@click.option('--write-subs/--no-write-subs', default=False,
              help='Guardar archivos de subtítulos en disco')
@click.option('--cookies-from', type=click.Choice(SUPPORTED_BROWSERS),
              help='Extraer cookies del navegador')
@click.option('--cookies-file', type=click.Path(exists=True),
              help='Ruta al archivo de cookies (ej. cookies.txt)')
@click.option('--notify/--no-notify', default=True,
              help='Mostrar notificación nativa de Windows Toast al finalizar')
@click.option('--archive/--no-archive', default=True,
              help='Usar archivo de historial para evitar re-descargas')
@click.option('--organize-by-platform/--no-organize-by-platform', default=True,
              help='Organizar descargas en subcarpetas por plataforma (ej. Descargas/Videos/TikTok/) (default: True)')
@click.option('--output', '-o', default='Descargas',
              help='Carpeta de salida')
@click.option('--concurrency', '-w', default=2, type=int,
              help='Número de descargas simultáneas en paralelo (1-8, default: 2)')
@click.option('--delay', '-d', default=1.0, type=float,
              help='Pausa en segundos entre inicios de descarga con jitter aleatorio (default: 1.0)')
def batch(
    file, quality, audio, audio_format, audio_quality, embed_thumbnail,
    subtitles, sub_lang, embed_subs, write_subs, cookies_from, cookies_file,
    notify, archive, organize_by_platform, output, concurrency, delay
):
    """
    Descarga múltiples videos/audios desde un archivo de texto (una URL por línea) con concurrencia multihilo de cualquier plataforma.
    """
    downloader = UniversalDownloader(output, use_archive=archive, organize_by_platform=organize_by_platform)
    downloader.download_batch(
        file,
        quality=quality,
        audio_only=audio,
        audio_format=audio_format,
        audio_quality=audio_quality,
        embed_thumbnail=embed_thumbnail,
        subtitles=subtitles,
        sub_lang=sub_lang,
        embed_subs=embed_subs,
        write_subs=write_subs,
        cookies_from=cookies_from,
        cookies_file=cookies_file,
        use_archive=archive,
        notify=notify,
        concurrency=concurrency,
        delay=delay,
        organize_by_platform=organize_by_platform
    )


@cli.command()
@click.argument('url', required=False)
@click.option('--quality', '-q', default='1080', 
              type=click.Choice(['720', '1080', '1440', '2160', 'best']),
              help='Calidad de descarga (default: 1080)')
@click.option('--audio', '-a', is_flag=True,
              help='Descargar solo audio')
@click.option('--audio-format', '-af', default='mp3',
              type=click.Choice(['mp3', 'flac', 'm4a', 'opus', 'wav']),
              help='Formato de audio deseado (default: mp3)')
@click.option('--audio-quality', '-aq', default='320',
              type=click.Choice(['320', '256', '192', '128']),
              help='Bitrate de audio en kbps (default: 320)')
@click.option('--embed-thumbnail/--no-thumbnail', default=True,
              help='Incrustar carátula/miniatura en el archivo de audio')
@click.option('--subtitles/--no-subtitles', default=False,
              help='Descargar subtítulos')
@click.option('--sub-lang', default='es,en,es-419',
              help='Idiomas de subtítulos (default: es,en,es-419)')
@click.option('--embed-subs/--no-embed-subs', default=True,
              help='Incrustar subtítulos en el video')
@click.option('--write-subs/--no-write-subs', default=False,
              help='Guardar archivos de subtítulos en disco')
@click.option('--cookies-from', type=click.Choice(SUPPORTED_BROWSERS),
              help='Extraer cookies del navegador')
@click.option('--cookies-file', type=click.Path(exists=True),
              help='Ruta al archivo de cookies (ej. cookies.txt)')
@click.option('--notify/--no-notify', default=True,
              help='Mostrar notificación nativa de Windows Toast al finalizar')
@click.option('--archive/--no-archive', default=True,
              help='Usar archivo de historial para evitar re-descargas')
@click.option('--organize-by-platform/--no-organize-by-platform', default=True,
              help='Organizar descargas en subcarpetas por plataforma (ej. Descargas/Videos/YouTube/) (default: True)')
@click.option('--output', '-o', default='Descargas',
              help='Carpeta de salida (default: Descargas)')
@click.option('--skip-errors', '-s', is_flag=True,
              help='Continuar descargando aunque fallen algunos elementos')
@click.option('--start', '-st', default=1, type=int,
              help='Número del elemento desde el que comenzar (default: 1)')
@click.option('--clipboard', '-c', is_flag=True,
              help='Usar automáticamente la URL del portapapeles')
def playlist(
    url, quality, audio, audio_format, audio_quality, embed_thumbnail,
    subtitles, sub_lang, embed_subs, write_subs, cookies_from, cookies_file,
    notify, archive, organize_by_platform, output, skip_errors, start, clipboard
):
    """
    Descarga una playlist, set de SoundCloud, álbum de Bandcamp, perfil o canal en orden con barras de progreso.
    """
    if clipboard:
        clip_url = get_clipboard_url()
        if clip_url:
            url = clip_url
        else:
            print_error("Portapapeles sin URL", "No se detectó ninguna URL multimedia en el portapapeles.")
            sys.exit(1)
    else:
        url = resolve_url(url, "Introduce la URL de la playlist, álbum, set o perfil")

    if not url:
        print_error("Operación cancelada", "No se ingresó ninguna URL.")
        sys.exit(1)

    downloader = UniversalDownloader(output, use_archive=archive, organize_by_platform=organize_by_platform)
    success = downloader.download_playlist(
        url,
        quality=quality,
        audio_only=audio,
        audio_format=audio_format,
        audio_quality=audio_quality,
        embed_thumbnail=embed_thumbnail,
        subtitles=subtitles,
        sub_lang=sub_lang,
        embed_subs=embed_subs,
        write_subs=write_subs,
        cookies_from=cookies_from,
        cookies_file=cookies_file,
        skip_errors=skip_errors,
        start_from=start,
        use_archive=archive,
        notify=notify,
        organize_by_platform=organize_by_platform
    )
    sys.exit(0 if success else 1)


@cli.command(name='cookies')
def cookies_cmd():
    """
    Diagnostica y muestra el estado de cookies de los navegadores y archivos de sesión.
    """
    check_cookies_status()


@cli.command(name='clipboard')
def check_clipboard():
    """
    Comprueba el portapapeles del sistema y muestra si contiene una URL multimedia válida.
    """
    clip_url = get_clipboard_url()
    if clip_url:
        platform_type, platform_name, badge_rich = detect_platform(clip_url)
        console.print(Panel(
            f"[bold green]✓ URL detectada en el portapapeles:[/bold green]\n"
            f"[bold white]🌐 Plataforma:[/bold white] {badge_rich}\n"
            f"[bold underline yellow]{clip_url}[/bold underline yellow]",
            title="[bold green]Portapapeles Listo[/bold green]",
            border_style="green",
            expand=False
        ))
    else:
        console.print(Panel(
            "[yellow]No se encontró ninguna URL válida en el portapapeles.[/yellow]\n"
            "[dim]Copia un enlace (YouTube, TikTok, Instagram, Twitter, Twitch, etc.) y vuelve a intentarlo.[/dim]",
            title="[bold yellow]Portapapeles Vacío[/bold yellow]",
            border_style="yellow",
            expand=False
        ))


if __name__ == '__main__':
    cli()
