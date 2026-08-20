"""
Módulo principal del descargador universal de medios (UniversalDownloader).
Gestiona la descarga de videos individuales, audios de alta fidelidad, listas de reproducción
y lotes concurrentes multihilo para YouTube, TikTok, Instagram, Twitter/X, Twitch, SoundCloud,
Bandcamp, Vimeo, Kick, streams directos HLS/DASH y web genérica.
"""

import os
import shutil
import time
import random
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List, Tuple

import yt_dlp
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.prompt import Confirm

from ui.console import (
    console,
    print_success,
    print_error,
    print_warning,
    print_info_panel,
    handle_download_error,
)
from ui.progress import (
    YtDlpQuietLogger,
    RichDownloadProgress,
    RichPlaylistProgress,
    RichConcurrentBatchProgress,
)
from ui.notifier import show_desktop_notification, get_notification_title
from core.cookies import get_cookie_opts
from core.extractor import get_raw_info, get_video_info, get_media_info, display_info
from utils.formatters import format_duration, format_bytes, sanitize_filename
from utils.platform_detector import (
    PlatformType,
    PlatformInfo,
    PLATFORM_FOLDER_NAMES,
    get_platform_folder_name,
    detect_platform,
    get_platform_info,
)


class UniversalDownloader:
    """
    Clase central para la gestión y descarga universal de contenidos multimedia.
    Soporta descarga de videos HD/4K, audios de alta fidelidad, playlists y lotes concurrentes multihilo
    para YouTube, TikTok, Instagram, Twitter/X, Twitch, SoundCloud, Bandcamp, Vimeo, streams directos y más.
    """
    def __init__(
        self,
        output_path: str = "Descargas",
        use_archive: bool = True,
        default_cookies_from: Optional[str] = None,
        default_cookies_file: Optional[str] = None,
        organize_by_platform: bool = True,
        console_instance: Optional[Console] = None
    ):
        self.console = console_instance or console
        self.output_path = Path(output_path)
        self.videos_path = self.output_path / "Videos"
        self.audios_path = self.output_path / "Audios"
        self.archive_file = self.output_path / ".download_archive.txt"
        self.use_archive = use_archive
        self.default_cookies_from = default_cookies_from
        self.default_cookies_file = default_cookies_file
        self.organize_by_platform = organize_by_platform
        
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.videos_path.mkdir(parents=True, exist_ok=True)
        self.audios_path.mkdir(parents=True, exist_ok=True)

        # Detectar runtimes de JavaScript disponibles (formato dict esperado por yt-dlp)
        self.js_runtimes: Dict[str, Any] = {}
        if shutil.which('deno'):
            self.js_runtimes['deno'] = {}
        if shutil.which('node'):
            self.js_runtimes['node'] = {}
        if shutil.which('bun'):
            self.js_runtimes['bun'] = {}

    def _get_target_folder(
        self,
        audio_only: bool = False,
        platform: Optional[PlatformType] = None,
        organize_by_platform: Optional[bool] = None
    ) -> Path:
        """Retorna la carpeta de destino según sea audio o video, con soporte opcional de subcarpetas por plataforma"""
        base_folder = self.audios_path if audio_only else self.videos_path
        should_organize = self.organize_by_platform if organize_by_platform is None else organize_by_platform
        if should_organize:
            folder = base_folder / get_platform_folder_name(platform)
        else:
            folder = base_folder
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _get_cookie_opts(
        self,
        url: Optional[str] = None,
        cookies_from: Optional[str] = None,
        cookies_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """Configura opciones de cookies delegando en el módulo cookies con resolución multi-sitio"""
        return get_cookie_opts(
            url=url,
            cookies_from=cookies_from,
            cookies_file=cookies_file,
            default_cookies_from=self.default_cookies_from,
            default_cookies_file=self.default_cookies_file
        )

    def _get_extractor_args(self, platform: PlatformType) -> Dict[str, Any]:
        """Configura extractor_args específicos según la plataforma detectada"""
        args: Dict[str, Any] = {}
        if platform == PlatformType.YOUTUBE:
            args['youtube'] = {'player_client': ['android', 'web', 'tv']}
        elif platform == PlatformType.TIKTOK:
            args['tiktok'] = {'app_version': 'latest'}
        return args

    def _get_audio_postprocessors(
        self,
        audio_format: str = "mp3",
        audio_quality: str = "320",
        embed_thumbnail: bool = True
    ) -> List[Dict[str, Any]]:
        """Genera la lista de postprocesadores para conversión de audio, metadatos y carátula"""
        fmt = 'm4a' if audio_format.lower() == 'aac' else audio_format.lower()
        
        postprocessors: List[Dict[str, Any]] = [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': fmt,
                'preferredquality': str(audio_quality) if fmt in ('mp3', 'm4a', 'opus') else None,
            },
            {
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }
        ]
        
        if embed_thumbnail and fmt in ('mp3', 'flac', 'm4a', 'opus'):
            postprocessors.extend([
                {
                    'key': 'FFmpegThumbnailsConvertor',
                    'format': 'jpg',
                },
                {
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                }
            ])
            
        return postprocessors

    def _get_format_string(
        self,
        quality: str,
        audio_only: bool,
        allow_merge: bool = True,
        platform: Optional[PlatformType] = None
    ) -> str:
        """
        Genera la cadena de formato para yt-dlp adaptada a la plataforma.
        - Streams separados (YouTube, Twitch, Reddit, Vimeo): bv*[height<=...]+ba/b[height<=...]/best
        - Streams progresivos directos (TikTok, Twitter/X, Instagram, streams directos): b[height<=...]/best/b
        - Audio puro: bestaudio/best
        """
        if audio_only:
            return 'bestaudio/best'

        # Plataformas con streams progresivos directos
        if platform in (PlatformType.TIKTOK, PlatformType.INSTAGRAM, PlatformType.TWITTER, PlatformType.DIRECT_STREAM):
            if quality == 'best':
                return 'b/best'
            return f"b[height<={quality}]/best/b"

        if quality == 'best':
            return 'bv*+ba/b/best' if allow_merge else 'b/best'

        if allow_merge:
            return f"bv*[height<={quality}]+ba/b[height<={quality}]/best"

        return f"b[height<={quality}]/best/b"

    def get_raw_info(
        self,
        url: str,
        cookies_from: Optional[str] = None,
        cookies_file: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Obtiene la información cruda completa de yt-dlp sin descargar"""
        return get_raw_info(
            url,
            js_runtimes=self.js_runtimes,
            cookies_from=cookies_from,
            cookies_file=cookies_file,
            default_cookies_from=self.default_cookies_from,
            default_cookies_file=self.default_cookies_file,
            console_instance=self.console
        )

    def get_video_info(
        self,
        url: str,
        cookies_from: Optional[str] = None,
        cookies_file: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Obtiene información estructurada y formatos del video o medio"""
        return get_video_info(
            url,
            js_runtimes=self.js_runtimes,
            cookies_from=cookies_from,
            cookies_file=cookies_file,
            default_cookies_from=self.default_cookies_from,
            default_cookies_file=self.default_cookies_file,
            console_instance=self.console
        )

    def get_media_info(
        self,
        url: str,
        cookies_from: Optional[str] = None,
        cookies_file: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Alias universal para obtener información estructurada de cualquier medio"""
        return self.get_video_info(
            url,
            cookies_from=cookies_from,
            cookies_file=cookies_file
        )

    def display_info(
        self,
        url: str,
        cookies_from: Optional[str] = None,
        cookies_file: Optional[str] = None
    ) -> None:
        """Muestra un panel visual con metadatos del medio y una tabla con los formatos disponibles"""
        display_info(
            url,
            js_runtimes=self.js_runtimes,
            cookies_from=cookies_from,
            cookies_file=cookies_file,
            default_cookies_from=self.default_cookies_from,
            default_cookies_file=self.default_cookies_file,
            console_instance=self.console
        )

    def download_video(
        self,
        url: str,
        quality: str = "1080",
        audio_only: bool = False,
        audio_format: str = "mp3",
        audio_quality: str = "320",
        embed_thumbnail: bool = True,
        subtitles: bool = False,
        sub_lang: str = "es,en,es-419",
        embed_subs: bool = True,
        write_subs: bool = False,
        cookies_from: Optional[str] = None,
        cookies_file: Optional[str] = None,
        use_archive: Optional[bool] = None,
        info_dict: Optional[Dict[str, Any]] = None,
        notify: bool = True,
        organize_by_platform: Optional[bool] = None,
    ) -> bool:
        """
        Descarga video o audio de cualquier plataforma soportada con soporte para:
        - Selector de resoluciones y formatos adaptativo por plataforma
        - Descarga e incrustación de subtítulos
        - Gestión y selección de cookies
        - Notificaciones nativas de Windows Toast
        """
        start_time = time.time()
        try:
            platform_type, platform_name, badge_rich = detect_platform(url)
            archive_active = self.use_archive if use_archive is None else use_archive
            has_ffmpeg = shutil.which('ffmpeg') is not None
            
            if not has_ffmpeg:
                print_warning(
                    "FFmpeg no está instalado en el sistema",
                    "• Para audios: FFmpeg es necesario para conversión y metadatos.\n"
                    "• Para videos: Se descargará en formato directo sin combinar streams.\n"
                    "• Para subtítulos: No se podrán incrustar directamente en el contenedor MP4.\n"
                    "• Instalación rápida: winget install ffmpeg (o ejecuta scripts/instalar_ffmpeg.bat)",
                    console_instance=self.console
                )
            
            if not self.js_runtimes and platform_type == PlatformType.YOUTUBE:
                print_warning(
                    "No se detectó JavaScript runtime (Deno, Node.js, Bun)",
                    "YouTube puede requerir un entorno JS para resolver challenges antibot.\n"
                    "Instala Deno recomendado: winget install DenoLand.Deno",
                    console_instance=self.console
                )
            
            target_folder = self._get_target_folder(audio_only, platform=platform_type, organize_by_platform=organize_by_platform)
            progress_manager = RichDownloadProgress(self.console)
            logger = YtDlpQuietLogger()
            
            ydl_opts: Dict[str, Any] = {
                'format': self._get_format_string(quality, audio_only, allow_merge=has_ffmpeg, platform=platform_type),
                'outtmpl': str(target_folder / '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'noprogress': True,
                'noplaylist': True,
                'logger': logger,
                'progress_hooks': [progress_manager.hook],
                'postprocessor_hooks': [progress_manager.postprocessor_hook],
                'socket_timeout': 30,
                'concurrent_fragment_downloads': 6,
                'retries': 10,
                'fragment_retries': 10,
                'extractor_retries': 5,
                'file_access_retries': 5,
                'extractor_args': self._get_extractor_args(platform_type),
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                },
            }
            
            if archive_active and self.archive_file:
                ydl_opts['download_archive'] = str(self.archive_file)
            
            if self.js_runtimes and platform_type == PlatformType.YOUTUBE:
                ydl_opts['js_runtimes'] = self.js_runtimes
                
            if has_ffmpeg and not audio_only:
                ydl_opts['ffmpeg_location'] = shutil.which('ffmpeg')
                ydl_opts['merge_output_format'] = 'mp4'
                
            if audio_only:
                if embed_thumbnail:
                    ydl_opts['writethumbnail'] = True
                ydl_opts['postprocessors'] = self._get_audio_postprocessors(
                    audio_format=audio_format,
                    audio_quality=audio_quality,
                    embed_thumbnail=embed_thumbnail
                )
            
            # Subtítulos
            if subtitles and not audio_only:
                langs = [l.strip() for l in sub_lang.split(',') if l.strip()]
                ydl_opts['writesubtitles'] = True
                ydl_opts['writeautomaticsub'] = True
                ydl_opts['subtitleslangs'] = langs if langs else ['es', 'en', 'es-419']
                ydl_opts['subtitlesformat'] = 'srt/vtt/best'
                if embed_subs and has_ffmpeg:
                    ydl_opts['embedsubtitles'] = True
                if write_subs or not embed_subs:
                    if has_ffmpeg:
                        ydl_opts.setdefault('postprocessors', []).append({
                            'key': 'FFmpegSubtitlesConvertor',
                            'format': 'srt'
                        })

            # Cookies
            cookie_opts = self._get_cookie_opts(url=url, cookies_from=cookies_from, cookies_file=cookies_file)
            ydl_opts.update(cookie_opts)
            
            # Reutilizar info_dict si ya fue obtenido en el selector interactivo
            info = info_dict
            if info is None:
                with self.console.status(f"[bold cyan]📥 Obteniendo información de {platform_name}...", spinner="dots"):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
            
            if info is None:
                print_info_panel("El contenido ya fue descargado previamente (registrado en el historial de descargas).", "Historial", console_instance=self.console)
                return True

            video_entry = info['entries'][0] if 'entries' in info and info['entries'] else info
            title = video_entry.get('title', 'Desconocido')
            duration = video_entry.get('duration', 0)
            uploader = video_entry.get('uploader') or video_entry.get('channel') or video_entry.get('artist') or video_entry.get('creator') or 'Desconocido'
            
            # Panel previo con detalles
            tipo_desc = f"Audio {audio_format.upper()} ({audio_quality} kbps)" if audio_only else f"Video {quality}p"
            subs_tag = f" • Subtítulos: {sub_lang}" if subtitles and not audio_only else ""
            meta_info = (
                f"[bold white]🌐 Plataforma:[/bold white] {badge_rich}\n"
                f"[bold white]📺 Título:[/bold white] [bold cyan]{title}[/bold cyan]\n"
                f"[bold white]👤 Autor / Canal:[/bold white] [yellow]{uploader}[/yellow]    "
                f"[bold white]⏱️  Duración:[/bold white] [green]{format_duration(duration)}[/green]    "
                f"[bold white]⚙️  Formato:[/bold white] [magenta]{tipo_desc}{subs_tag}[/magenta]"
            )
            self.console.print(Panel(meta_info, title="[bold cyan]⬇️  Iniciando Descarga[/bold cyan]", border_style="cyan", expand=False))

            # Ejecución de descarga con barra de progreso Rich
            with progress_manager.progress:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.process_ie_result(info, download=True)
                    filename = ydl.prepare_filename(video_entry)
                    if audio_only:
                        audio_ext = 'm4a' if audio_format.lower() == 'aac' else audio_format.lower()
                        filename = str(Path(filename).with_suffix(f'.{audio_ext}'))

            # Obtener tamaño real en disco si existe
            saved_path = Path(filename)
            size_str = ""
            file_bytes = 0
            if saved_path.exists():
                file_bytes = saved_path.stat().st_size
                size_str = f" • Tamaño: {format_bytes(file_bytes)}"

            print_success(
                "¡Descarga completada con éxito!",
                f"📁 Archivo: {saved_path.name}\n"
                f"📂 Ruta: {saved_path.parent}{size_str}",
                console_instance=self.console
            )

            # Notificación Windows Toast para descargas largas
            elapsed = time.time() - start_time
            if notify and (duration >= 60 or elapsed >= 30):
                notif_title = get_notification_title(platform_type, audio_only=audio_only)
                notif_msg = f"{title}\nDuración: {format_duration(duration)}{size_str}"
                show_desktop_notification(notif_title, notif_msg, saved_path.parent)

            return True

        except Exception as e:
            handle_download_error(e, url, console_instance=self.console)
            return False

    def download_playlist(
        self,
        url: str,
        quality: str = "1080",
        audio_only: bool = False,
        audio_format: str = "mp3",
        audio_quality: str = "320",
        embed_thumbnail: bool = True,
        subtitles: bool = False,
        sub_lang: str = "es,en,es-419",
        embed_subs: bool = True,
        write_subs: bool = False,
        cookies_from: Optional[str] = None,
        cookies_file: Optional[str] = None,
        skip_errors: bool = False,
        start_from: int = 1,
        use_archive: Optional[bool] = None,
        notify: bool = True,
        organize_by_platform: Optional[bool] = None,
    ) -> bool:
        """
        Descarga una playlist, set, álbum o colección de cualquier plataforma en orden con barras de progreso Rich
        """
        try:
            platform_type, platform_name, badge_rich = detect_platform(url)
            archive_active = self.use_archive if use_archive is None else use_archive
            
            if not self.js_runtimes and platform_type == PlatformType.YOUTUBE:
                print_warning(
                    "No se detectó JavaScript runtime",
                    "YouTube requiere Deno o Node.js para extraer algunos videos de la playlist.\n"
                    "Instala Deno recomendado: winget install DenoLand.Deno",
                    console_instance=self.console
                )
                if not Confirm.ask("¿Deseas continuar de todos modos? (algunos elementos podrían fallar)", default=False, console=self.console):
                    return False
            
            flat_opts: Dict[str, Any] = {
                'extract_flat': True,
                'quiet': True,
                'no_warnings': True,
                'extractor_args': self._get_extractor_args(platform_type),
            }
            if self.js_runtimes and platform_type == PlatformType.YOUTUBE:
                flat_opts['js_runtimes'] = self.js_runtimes
                
            cookie_opts = self._get_cookie_opts(url=url, cookies_from=cookies_from, cookies_file=cookies_file)
            flat_opts.update(cookie_opts)
            
            with self.console.status(f"[bold cyan]📥 Obteniendo información de la lista de {platform_name}...", spinner="dots"):
                with yt_dlp.YoutubeDL(flat_opts) as ydl:
                    playlist_info = ydl.extract_info(url, download=False)
            
            if not playlist_info:
                print_error(
                    "No se pudo acceder a la lista",
                    f"Verifica que el enlace de {platform_name} sea público o accesible.",
                    console_instance=self.console
                )
                return False
            
            playlist_title = playlist_info.get('title', f'Lista {platform_name}')
            if 'entries' in playlist_info and playlist_info['entries']:
                entries = [e for e in playlist_info['entries'] if e]
            elif playlist_info.get('_type') == 'playlist':
                entries = [e for e in playlist_info.get('entries', []) if e]
            else:
                entries = [playlist_info]

            total_videos = len(entries)
            if total_videos == 0:
                print_error("Lista vacía", f"No se encontraron elementos descargables en este enlace de {platform_name}.", console_instance=self.console)
                return False
            
            safe_playlist_name = sanitize_filename(playlist_title)
            target_base = self._get_target_folder(audio_only, platform=platform_type, organize_by_platform=organize_by_platform)
            playlist_folder = target_base / safe_playlist_name
            playlist_folder.mkdir(parents=True, exist_ok=True)
            
            # Panel de Información de la Playlist
            tipo_desc = f"Audio {audio_format.upper()} ({audio_quality} kbps)" if audio_only else f"Video {quality}p"
            subs_tag = f" • Subtítulos: {sub_lang}" if subtitles and not audio_only else ""
            p_info = (
                f"[bold white]🌐 Plataforma:[/bold white] {badge_rich}\n"
                f"[bold white]📺 Lista / Álbum:[/bold white] [bold cyan]{playlist_title}[/bold cyan]\n"
                f"[bold white]📊 Total elementos:[/bold white] [yellow]{total_videos}[/yellow]    "
                f"[bold white]⚙️  Formato:[/bold white] [magenta]{tipo_desc}{subs_tag}[/magenta]    "
                f"[bold white]▶️  Inicio:[/bold white] [green]Elemento #{start_from}[/green]\n"
                f"[bold white]📁 Carpeta:[/bold white] [dim]{playlist_folder}[/dim]"
            )
            self.console.print(Panel(p_info, title=f"[bold cyan]📋 Descarga de Lista ({platform_name})[/bold cyan]", border_style="cyan", expand=False))
            
            has_ffmpeg = shutil.which('ffmpeg') is not None
            playlist_progress = RichPlaylistProgress(self.console)
            playlist_progress.setup(total_videos, playlist_title)
            logger = YtDlpQuietLogger()

            ydl_opts: Dict[str, Any] = {
                'format': self._get_format_string(quality, audio_only, allow_merge=has_ffmpeg, platform=platform_type),
                'outtmpl': str(playlist_folder / '%(playlist_index)03d - %(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'noprogress': True,
                'logger': logger,
                'progress_hooks': [playlist_progress.hook],
                'postprocessor_hooks': [playlist_progress.postprocessor_hook],
                'socket_timeout': 30,
                'ignoreerrors': skip_errors,
                'noplaylist': False,
                'yes_playlist': True,
                'playliststart': start_from,
                'playlistreverse': False,
                'playlistrandom': False,
                'concurrent_fragment_downloads': 6,
                'retries': 10,
                'fragment_retries': 10,
                'extractor_retries': 5,
                'file_access_retries': 5,
                'extractor_args': self._get_extractor_args(platform_type),
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                },
            }
            
            if archive_active and self.archive_file:
                ydl_opts['download_archive'] = str(self.archive_file)
            if self.js_runtimes and platform_type == PlatformType.YOUTUBE:
                ydl_opts['js_runtimes'] = self.js_runtimes
            if has_ffmpeg and not audio_only:
                ydl_opts['ffmpeg_location'] = shutil.which('ffmpeg')
                ydl_opts['merge_output_format'] = 'mp4'
            
            ydl_opts.update(cookie_opts)
            
            if audio_only:
                if embed_thumbnail:
                    ydl_opts['writethumbnail'] = True
                ydl_opts['postprocessors'] = self._get_audio_postprocessors(
                    audio_format=audio_format,
                    audio_quality=audio_quality,
                    embed_thumbnail=embed_thumbnail
                )
            
            # Subtítulos
            if subtitles and not audio_only:
                langs = [l.strip() for l in sub_lang.split(',') if l.strip()]
                ydl_opts['writesubtitles'] = True
                ydl_opts['writeautomaticsub'] = True
                ydl_opts['subtitleslangs'] = langs if langs else ['es', 'en', 'es-419']
                ydl_opts['subtitlesformat'] = 'srt/vtt/best'
                if embed_subs and has_ffmpeg:
                    ydl_opts['embedsubtitles'] = True
                if write_subs or not embed_subs:
                    if has_ffmpeg:
                        ydl_opts.setdefault('postprocessors', []).append({
                            'key': 'FFmpegSubtitlesConvertor',
                            'format': 'srt'
                        })
            
            try:
                with Live(playlist_progress.group, console=self.console, refresh_per_second=10):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
            except Exception as e:
                if not skip_errors:
                    handle_download_error(e, url, console_instance=self.console)
                    return False

            # Contar archivos en la carpeta
            downloaded_files = list(playlist_folder.glob('*'))
            downloaded_count = len([f for f in downloaded_files if f.is_file()])
            
            print_success(
                "¡Proceso de lista completado!",
                f"📊 Elementos guardados: {downloaded_count} de {total_videos} elementos\n"
                f"📁 Carpeta de destino: {playlist_folder}",
                console_instance=self.console
            )

            # Notificación Windows Toast
            if notify:
                notif_title = get_notification_title(platform_type, audio_only=audio_only, is_playlist=True)
                show_desktop_notification(
                    notif_title,
                    f"{playlist_title}\nGuardados: {downloaded_count}/{total_videos} elementos",
                    playlist_folder
                )

            return True
            
        except Exception as e:
            handle_download_error(e, url, console_instance=self.console)
            return False

    def download_batch(
        self,
        file_path: str,
        quality: str = "1080",
        audio_only: bool = False,
        audio_format: str = "mp3",
        audio_quality: str = "320",
        embed_thumbnail: bool = True,
        subtitles: bool = False,
        sub_lang: str = "es,en,es-419",
        embed_subs: bool = True,
        write_subs: bool = False,
        cookies_from: Optional[str] = None,
        cookies_file: Optional[str] = None,
        use_archive: Optional[bool] = None,
        notify: bool = True,
        concurrency: int = 2,
        delay: float = 1.0,
        organize_by_platform: Optional[bool] = None,
    ) -> bool:
        """
        Descarga múltiples medios desde un archivo de texto con URLs de cualquier plataforma soportando:
        - Concurrencia multihilo controlada (ThreadPoolExecutor) con --concurrency / -w
        - Control de pausas con jitter aleatorio inteligente (--delay / -d ±0.5s) para evitar límites de tasa
        - Barras de progreso simultáneas en paralelo con Rich
        """
        try:
            p = Path(file_path)
            if not p.exists():
                print_error("Archivo no encontrado", f"No existe el archivo {file_path}", console_instance=self.console)
                return False

            with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            if not urls:
                print_error("Archivo vacío", "No se encontraron URLs válidas en el archivo.", console_instance=self.console)
                return False

            archive_active = self.use_archive if use_archive is None else use_archive
            has_ffmpeg = shutil.which('ffmpeg') is not None
            target_folder = self.audios_path if audio_only else self.videos_path
            workers = max(1, min(concurrency, len(urls), 8))

            tipo_desc = f"Audio {audio_format.upper()} ({audio_quality} kbps)" if audio_only else f"Video {quality}p"
            subs_tag = f" • Subtítulos: {sub_lang}" if subtitles and not audio_only else ""
            delay_tag = f" • Pausa entre hilos: {delay}s (±0.5s jitter)" if delay > 0 else ""
            
            self.console.print(Panel(
                f"[bold white]📋 Archivo de lote:[/bold white] [bold cyan]{file_path}[/bold cyan]\n"
                f"[bold white]📊 Total URLs a descargar:[/bold white] [yellow]{len(urls)}[/yellow]    "
                f"[bold white]⚡ Concurrencia:[/bold white] [green]{workers} workers simultáneos[/green]{delay_tag}\n"
                f"[bold white]⚙️  Formato de salida:[/bold white] [magenta]{tipo_desc}{subs_tag}[/magenta]\n"
                f"[bold white]📁 Carpeta de destino:[/bold white] [dim]{target_folder}[/dim]",
                title="[bold cyan]📦 Descarga en Lote Concurrente Universal[/bold cyan]",
                border_style="cyan",
                expand=False
            ))

            batch_progress = RichConcurrentBatchProgress(self.console)
            batch_progress.setup(len(urls), title=f"Lote: {p.name}")

            completed_lock = threading.Lock()
            completed_counter = [0]
            results: List[Tuple[int, str, bool, str]] = []

            def _worker_task(item_idx: int, url: str, worker_id: int) -> Tuple[int, str, bool, str]:
                item_platform, item_plat_name, _ = detect_platform(url)

                # Pausa inteligente con jitter aleatorio para no saturar IP
                if delay > 0 and item_idx > 1:
                    jitter = random.uniform(-0.5, 0.5)
                    sleep_duration = max(0.0, delay + jitter)
                    time.sleep(sleep_duration)

                progress_hook, postprocessor_hook, cleanup = batch_progress.create_hooks_for_item(
                    item_idx=item_idx,
                    total_items=len(urls),
                    worker_id=worker_id
                )

                item_folder = self._get_target_folder(audio_only, platform=item_platform, organize_by_platform=organize_by_platform)
                logger = YtDlpQuietLogger()
                ydl_opts: Dict[str, Any] = {
                    'format': self._get_format_string(quality, audio_only, allow_merge=has_ffmpeg, platform=item_platform),
                    'outtmpl': str(item_folder / '%(title)s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'noprogress': True,
                    'noplaylist': True,
                    'logger': logger,
                    'progress_hooks': [progress_hook],
                    'postprocessor_hooks': [postprocessor_hook],
                    'socket_timeout': 30,
                    'concurrent_fragment_downloads': 6,
                    'retries': 10,
                    'fragment_retries': 10,
                    'extractor_retries': 5,
                    'file_access_retries': 5,
                    'extractor_args': self._get_extractor_args(item_platform),
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    },
                }

                if archive_active and self.archive_file:
                    ydl_opts['download_archive'] = str(self.archive_file)
                if self.js_runtimes and item_platform == PlatformType.YOUTUBE:
                    ydl_opts['js_runtimes'] = self.js_runtimes
                if has_ffmpeg and not audio_only:
                    ydl_opts['ffmpeg_location'] = shutil.which('ffmpeg')
                    ydl_opts['merge_output_format'] = 'mp4'

                if audio_only:
                    if embed_thumbnail:
                        ydl_opts['writethumbnail'] = True
                    ydl_opts['postprocessors'] = self._get_audio_postprocessors(
                        audio_format=audio_format,
                        audio_quality=audio_quality,
                        embed_thumbnail=embed_thumbnail
                    )

                if subtitles and not audio_only:
                    langs = [l.strip() for l in sub_lang.split(',') if l.strip()]
                    ydl_opts['writesubtitles'] = True
                    ydl_opts['writeautomaticsub'] = True
                    ydl_opts['subtitleslangs'] = langs if langs else ['es', 'en', 'es-419']
                    ydl_opts['subtitlesformat'] = 'srt/vtt/best'
                    if embed_subs and has_ffmpeg:
                        ydl_opts['embedsubtitles'] = True
                    if write_subs or not embed_subs:
                        if has_ffmpeg:
                            ydl_opts.setdefault('postprocessors', []).append({
                                'key': 'FFmpegSubtitlesConvertor',
                                'format': 'srt'
                            })

                cookie_opts = self._get_cookie_opts(url=url, cookies_from=cookies_from, cookies_file=cookies_file)
                ydl_opts.update(cookie_opts)

                success = False
                err_msg = ""
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    success = True
                except Exception as ex:
                    success = False
                    err_msg = str(ex)
                finally:
                    cleanup()
                    with completed_lock:
                        completed_counter[0] += 1
                        batch_progress.advance_overall(completed_counter[0])

                return (item_idx, url, success, err_msg)

            # Ejecutar descargas concurrentes en el pool de hilos
            with batch_progress.progress:
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = {
                        executor.submit(_worker_task, idx, u, (idx % workers) + 1): idx
                        for idx, u in enumerate(urls, 1)
                    }
                    for future in as_completed(futures):
                        try:
                            res = future.result()
                            results.append(res)
                        except Exception as e:
                            idx = futures[future]
                            results.append((idx, urls[idx - 1], False, str(e)))

            # Ordenar resultados por índice original
            results.sort(key=lambda x: x[0])
            success_count = sum(1 for r in results if r[2])
            failed_count = len(urls) - success_count

            # Tabla resumen de resultados del lote
            res_table = Table(
                title=f"[bold cyan]📊 Resumen del Lote ({p.name})[/bold cyan]",
                header_style="bold magenta",
                border_style="cyan"
            )
            res_table.add_column("#", style="dim", justify="center")
            res_table.add_column("URL / Enlace", style="bold white", justify="left")
            res_table.add_column("Estado", justify="center")
            res_table.add_column("Detalles", justify="left")

            for idx, u, ok, err in results:
                short_u = u if len(u) <= 45 else u[:42] + "..."
                if ok:
                    res_table.add_row(str(idx), short_u, "[bold green]✅ Completado[/bold green]", "[green]Descargado / Actualizado[/green]")
                else:
                    short_err = err if len(err) <= 50 else err[:47] + "..."
                    res_table.add_row(str(idx), short_u, "[bold red]✗ Fallido[/bold red]", f"[red]{short_err}[/red]")

            self.console.print()
            self.console.print(res_table)
            self.console.print()

            if success_count > 0:
                print_success(
                    "Resumen de descarga en lote",
                    f"✅ Completadas con éxito: {success_count}/{len(urls)} descargas."
                    + (f"\n⚠️ Fallidas: {failed_count}" if failed_count > 0 else ""),
                    console_instance=self.console
                )
            else:
                print_error(
                    "Fallo en descarga de lote",
                    f"No se pudo completar ninguna de las {len(urls)} descargas.",
                    console_instance=self.console
                )

            # Notificación Windows Toast
            if notify:
                notif_title = get_notification_title(PlatformType.GENERIC, is_batch=True)
                show_desktop_notification(
                    notif_title,
                    f"Archivo: {p.name}\nExitosas: {success_count}/{len(urls)} descargas",
                    target_folder
                )

            return success_count > 0

        except Exception as e:
            handle_download_error(e, file_path, console_instance=self.console)
            return False


# ==============================================================================
# Backward compatibility aliases
# ==============================================================================
YouTubeDownloader = UniversalDownloader
MediaDownloader = UniversalDownloader
