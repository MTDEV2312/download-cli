"""
Módulo principal del descargador universal de medios (UniversalDownloader).
Gestiona la descarga de videos individuales, audios de alta fidelidad, listas de reproducción
y lotes concurrentes multihilo para YouTube, TikTok, Instagram, Twitter/X, Twitch, SoundCloud,
Bandcamp, Vimeo, Kick, streams directos HLS/DASH y web genérica.
"""

import os
import re
import sys
import shutil
import time
import random
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List, Tuple, Set

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
    prompt_interactive_recovery,
)
from ui.progress import (
    YtDlpQuietLogger,
    RichDownloadProgress,
    RichPlaylistProgress,
    RichConcurrentBatchProgress,
)
from ui.notifier import show_desktop_notification, get_notification_title
from core.cookies import get_cookie_opts
from core.extractor import (
    get_raw_info,
    get_video_info,
    get_media_info,
    display_info,
    FALLBACK_PLAYER_CLIENTS,
    extract_info_with_client_fallback,
)
from utils.formatters import format_duration, format_bytes, sanitize_filename
from utils.platform_detector import (
    PlatformType,
    PlatformInfo,
    PLATFORM_FOLDER_NAMES,
    get_platform_folder_name,
    detect_platform,
    get_platform_info,
)


def calculate_pacing_delay(
    sleep_interval: Optional[float] = None,
    max_sleep_interval: Optional[float] = None,
    default_pacing: bool = True
) -> float:
    """
    Calcula la duración de la pausa en segundos con jitter aleatorio uniforme:
    - Si sleep_interval == 0 and (max_sleep_interval is None or max_sleep_interval == 0): retorna 0.0 (override explícito)
    - Si se especifican sleep_interval y max_sleep_interval: retorna random.uniform(min_val, max_val)
    - Si solo se especifica sleep_interval > 0: retorna max(0.0, sleep_interval + random.uniform(-0.5, 0.5))
    - Si solo se especifica max_sleep_interval > 0: retorna random.uniform(0.0, max_sleep_interval)
    - Si ambos son None y default_pacing=True: retorna polite default 1.0s ± 0.5s -> random.uniform(0.5, 1.5)
    - Si ambos son None y default_pacing=False: retorna 0.0
    """
    if sleep_interval is not None and max_sleep_interval is not None:
        s = float(sleep_interval)
        m = float(max_sleep_interval)
        if s == 0.0 and m == 0.0:
            return 0.0
        low = min(s, m)
        high = max(s, m)
        return random.uniform(low, high)

    if sleep_interval is not None and max_sleep_interval is None:
        s = float(sleep_interval)
        if s == 0.0:
            return 0.0
        jitter = random.uniform(-0.5, 0.5)
        return max(0.0, s + jitter)

    if sleep_interval is None and max_sleep_interval is not None:
        m = float(max_sleep_interval)
        if m == 0.0:
            return 0.0
        return random.uniform(0.0, m)

    if default_pacing:
        return random.uniform(0.5, 1.5)

    return 0.0


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
        self.cookies_path = Path("cookies")
        self.cookies_path.mkdir(parents=True, exist_ok=True)

        # Detectar runtimes de JavaScript disponibles (formato dict esperado por yt-dlp)
        self.js_runtimes: Dict[str, Any] = {}
        if shutil.which('deno'):
            self.js_runtimes['deno'] = {}
        if shutil.which('node'):
            self.js_runtimes['node'] = {}
        if shutil.which('bun'):
            self.js_runtimes['bun'] = {}

    def _extract_possible_ids_from_url(self, url: str) -> List[str]:
        """Extrae posibles identificadores de medios a partir de la URL para cotejo con download_archive."""
        if not url:
            return []
        ids: Set[str] = set()
        clean_url = url.strip()

        # Twitter / X: status/123456789
        m_tw = re.search(r'(?:twitter\.com|x\.com)/(?:[^/]+/status/|status/|i/web/status/)(\d+)', clean_url)
        if m_tw:
            ids.add(m_tw.group(1))

        # YouTube: watch?v=ID, youtu.be/ID, shorts/ID, embed/ID
        m_yt = re.search(r'(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|embed/|v/|shorts/))([a-zA-Z0-9_-]{11})', clean_url)
        if m_yt:
            ids.add(m_yt.group(1))

        # Instagram: /p/ID, /reel/ID, /tv/ID
        m_ig = re.search(r'instagram\.com/(?:p|reel|tv)/([a-zA-Z0-9_-]+)', clean_url)
        if m_ig:
            ids.add(m_ig.group(1))

        # TikTok: /video/123456789
        m_tt = re.search(r'tiktok\.com/@[^/]+/video/(\d+)', clean_url)
        if m_tt:
            ids.add(m_tt.group(1))

        # Twitch: /videos/123456789
        m_tw_vid = re.search(r'twitch\.tv/videos/(\d+)', clean_url)
        if m_tw_vid:
            v_id = m_tw_vid.group(1)
            ids.add(v_id)
            ids.add(f"v{v_id}")

        # Kick: /videos/<uuid> o ?clip=<clip_id> o /clips/<clip_id>
        m_kick_vod = re.search(r'kick\.com/(?:[\w-]+/videos/|video/)([\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12})', clean_url, re.IGNORECASE)
        if m_kick_vod:
            ids.add(m_kick_vod.group(1))

        m_kick_clip = re.search(r'kick\.com/[\w-]+(?:/clips/|/?\?(?:[^#]+&)?clip=)(clip_[\w-]+)', clean_url, re.IGNORECASE)
        if m_kick_clip:
            ids.add(m_kick_clip.group(1))

        # Último segmento alfanumérico del path si parece un ID
        try:
            from urllib.parse import urlparse
            path = urlparse(clean_url).path.rstrip('/')
            if path:
                last_segment = path.split('/')[-1]
                if last_segment and len(last_segment) >= 4 and not last_segment.endswith(('.html', '.php', '.asp')):
                    ids.add(last_segment)
        except Exception:
            pass

        return list(ids)

    def _is_in_download_archive(self, url: str) -> bool:
        """Determina si la URL o el ID de medio ya se encuentra registrado en el archivo .download_archive.txt."""
        if not self.archive_file or not self.archive_file.exists():
            return False
        try:
            candidate_ids = set(self._extract_possible_ids_from_url(url))
            with open(self.archive_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        continue
                    parts = stripped.split()
                    if len(parts) >= 2:
                        archive_id = parts[1]
                        if archive_id in candidate_ids:
                            return True
                    if url in stripped or (len(parts) == 1 and parts[0] in candidate_ids):
                        return True
        except Exception:
            return False
        return False

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
        sleep_interval: Optional[float] = None,
        max_sleep_interval: Optional[float] = None,
        interactive: bool = False,
    ) -> bool:
        """
        Descarga video o audio de cualquier plataforma soportada con soporte para:
        - Selector de resoluciones y formatos adaptativo por plataforma
        - Descarga e incrustación de subtítulos
        - Gestión y selección de cookies (con soporte de perfiles browser:profile)
        - Rotación automática de clientes YouTube ante bloqueos 403
        - Recuperación interactiva en terminal TTY
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

            # Cookies: si info_dict ya fue autenticado previamente, reutilizar sus cookies
            using_cookies = False
            if info_dict and info_dict.get('_used_cookies') and info_dict.get('_cookie_opts'):
                ydl_opts.update(info_dict['_cookie_opts'])
                using_cookies = True
            
            # Reutilizar info_dict si ya fue obtenido en el selector interactivo o extraer con fallback
            info = info_dict
            active_client = None
            if info is None:
                # Fase 1: Intento sin cookies
                with self.console.status(f"[bold cyan]📥 Obteniendo información de {platform_name}...", spinner="dots"):
                    info, active_client = extract_info_with_client_fallback(
                        url,
                        base_ydl_opts=dict(ydl_opts),
                        console_instance=self.console,
                        suppress_error_log=True
                    )
            
            if info is None:
                # Comprobar si se trata de un elemento ya registrado en el download_archive
                if archive_active and self._is_in_download_archive(url):
                    print_info_panel(
                        "El contenido ya fue descargado previamente (registrado en el historial de descargas).",
                        "Descarga Omitida",
                        console_instance=self.console
                    )
                    return True

                # Fase 2: Si falló sin cookies, reintentar con cookies si están disponibles
                if not using_cookies:
                    cookie_opts = self._get_cookie_opts(url=url, cookies_from=cookies_from, cookies_file=cookies_file)
                    if cookie_opts:
                        self.console.print("[dim cyan]ℹ️ Extracción sin cookies falló o requiere sesión. Reintentando con cookies...[/dim cyan]")
                        ydl_opts.update(cookie_opts)
                        using_cookies = True
                        with self.console.status(f"[bold cyan]📥 Obteniendo información autenticada de {platform_name}...", spinner="dots"):
                            info, active_client = extract_info_with_client_fallback(
                                url,
                                base_ydl_opts=dict(ydl_opts),
                                console_instance=self.console,
                                suppress_error_log=False
                            )

            if info is None:
                # Si no se recuperó ni con cookies, emitir diagnóstico final
                if not using_cookies:
                    extract_info_with_client_fallback(
                        url,
                        base_ydl_opts=ydl_opts,
                        console_instance=self.console,
                        suppress_error_log=False
                    )
                return False

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

            # Ejecución de descarga con barra de progreso Rich y fallback de streaming 403
            download_done = False
            candidates = [active_client] if active_client else []
            for c_name in FALLBACK_PLAYER_CLIENTS:
                if c_name not in candidates:
                    candidates.append(c_name)

            for cand_client in candidates:
                if platform_type == PlatformType.YOUTUBE and cand_client:
                    ext_args = dict(ydl_opts.get('extractor_args', {}))
                    yt_args = dict(ext_args.get('youtube', {}))
                    yt_args['player_client'] = [cand_client]
                    ext_args['youtube'] = yt_args
                    ydl_opts['extractor_args'] = ext_args

                try:
                    with progress_manager.progress:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.process_ie_result(info, download=True)
                            filename = ydl.prepare_filename(video_entry)
                            if audio_only:
                                audio_ext = 'm4a' if audio_format.lower() == 'aac' else audio_format.lower()
                                filename = str(Path(filename).with_suffix(f'.{audio_ext}'))
                    download_done = True
                    break
                except Exception as stream_err:
                    err_str = str(stream_err).lower()
                    if ("403" in err_str or "forbidden" in err_str) and platform_type == PlatformType.YOUTUBE and cand_client != candidates[-1]:
                        self.console.print(f"[dim cyan]ℹ️ Error 403 en streaming. Rotando a cliente: '{candidates[candidates.index(cand_client)+1]}'[/dim cyan]")
                        # Re-extraer metadatos con el nuevo cliente para refrescar URLs de stream
                        next_client = candidates[candidates.index(cand_client)+1]
                        ext_args = dict(ydl_opts.get('extractor_args', {}))
                        yt_args = dict(ext_args.get('youtube', {}))
                        yt_args['player_client'] = [next_client]
                        ext_args['youtube'] = yt_args
                        ydl_opts['extractor_args'] = ext_args
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl_refresh:
                            refreshed_info = ydl_refresh.extract_info(url, download=False)
                            if refreshed_info:
                                info = refreshed_info
                                video_entry = info['entries'][0] if 'entries' in info and info['entries'] else info
                        continue
                    else:
                        if not using_cookies:
                            cookie_opts = self._get_cookie_opts(url=url, cookies_from=cookies_from, cookies_file=cookies_file)
                            if cookie_opts:
                                self.console.print("[dim cyan]ℹ️ Descarga de stream sin cookies rechazada. Reintentando con sesión de cookies...[/dim cyan]")
                                ydl_opts.update(cookie_opts)
                                using_cookies = True
                                try:
                                    with yt_dlp.YoutubeDL(ydl_opts) as ydl_auth_refresh:
                                        refreshed_info = ydl_auth_refresh.extract_info(url, download=False)
                                        if refreshed_info:
                                            info = refreshed_info
                                            video_entry = info['entries'][0] if 'entries' in info and info['entries'] else info
                                    with progress_manager.progress:
                                        with yt_dlp.YoutubeDL(ydl_opts) as ydl_auth_dl:
                                            ydl_auth_dl.process_ie_result(info, download=True)
                                            filename = ydl_auth_dl.prepare_filename(video_entry)
                                            if audio_only:
                                                audio_ext = 'm4a' if audio_format.lower() == 'aac' else audio_format.lower()
                                                filename = str(Path(filename).with_suffix(f'.{audio_ext}'))
                                    download_done = True
                                    break
                                except Exception as auth_stream_err:
                                    raise auth_stream_err
                        raise stream_err

            if not download_done:
                return False

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
        skip_errors: bool = True,
        abort_on_error: bool = False,
        start_from: int = 1,
        use_archive: Optional[bool] = None,
        notify: bool = True,
        organize_by_platform: Optional[bool] = None,
        sleep_interval: Optional[float] = None,
        max_sleep_interval: Optional[float] = None,
        interactive: bool = False,
        max_retries: int = 3,
    ) -> bool:
        """
        Descarga una playlist, set, álbum o colección de cualquier plataforma de forma resiliente y tolerante a fallos:
        - Aislamiento de errores por elemento individual (skip_errors=True por defecto)
        - Reintentos automáticos con retroceso exponencial (exponential backoff)
        - Rotación automática de clientes YouTube ante 403 Forbidden / desafíos antibot
        - Control de pausas con jitter aleatorio (--sleep-interval y --max-sleep-interval)
        - Menú de recuperación interactiva ante bloqueos en terminal TTY
        - Tabla Rich estructurada de auditoría post-ejecución con resumen global
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

            # Fase 1: Extracción plana de la lista sin cookies
            flat_info = None
            try:
                with self.console.status(f"[bold cyan]📥 Obteniendo información de la lista de {platform_name}...", spinner="dots"):
                    with yt_dlp.YoutubeDL(flat_opts) as ydl:
                        flat_info = ydl.extract_info(url, download=False)
            except Exception:
                flat_info = None

            # Fase 2: Si falló sin cookies, reintentar con cookies si están disponibles
            if not flat_info:
                cookie_opts = self._get_cookie_opts(url=url, cookies_from=cookies_from, cookies_file=cookies_file)
                if cookie_opts:
                    self.console.print(f"[dim cyan]ℹ️ Lista no accesible sin cookies. Reintentando con sesión de cookies...[/dim cyan]")
                    flat_opts.update(cookie_opts)
                    try:
                        with self.console.status(f"[bold cyan]📥 Obteniendo información autenticada de la lista de {platform_name}...", spinner="dots"):
                            with yt_dlp.YoutubeDL(flat_opts) as ydl:
                                flat_info = ydl.extract_info(url, download=False)
                    except Exception:
                        flat_info = None

            playlist_info = flat_info
            
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
            self.console.print(Panel(p_info, title=f"[bold cyan]📋 Descarga Resiliente de Lista ({platform_name})[/bold cyan]", border_style="cyan", expand=False))
            
            has_ffmpeg = shutil.which('ffmpeg') is not None
            playlist_progress = RichPlaylistProgress(self.console)
            playlist_progress.setup(total_videos, playlist_title)

            # Preparar cola y estructura de auditoría
            effective_abort = abort_on_error or (not skip_errors)
            items_to_download = [(i, entry) for i, entry in enumerate(entries, 1) if i >= start_from]
            results: List[Dict[str, Any]] = []

            # Loop aislado por elemento con retroceso exponencial y rotación
            for loop_idx, (item_num, entry) in enumerate(items_to_download):
                # Aplicar pausa con jitter aleatorio entre elementos consecutivos
                if loop_idx > 0:
                    pacing_delay = calculate_pacing_delay(sleep_interval, max_sleep_interval, default_pacing=True)
                    if pacing_delay > 0:
                        time.sleep(pacing_delay)

                item_url = entry.get('url') or entry.get('webpage_url') or entry.get('original_url') or url
                if not str(item_url).startswith('http'):
                    if platform_type == PlatformType.YOUTUBE and entry.get('id'):
                        item_url = f"https://www.youtube.com/watch?v={entry['id']}"
                    elif entry.get('id'):
                        item_url = entry['id']
                    else:
                        item_url = url

                item_title = entry.get('title') or f"Elemento #{item_num}"
                item_success = False
                item_skipped = False
                item_reason = ""
                start_item_time = time.time()

                # Estado de rotación de cliente y cookies para este elemento (empieza sin cookies)
                curr_client = None
                curr_cookies_from = None
                curr_cookies_file = None
                using_item_cookies = False
                client_candidates = list(FALLBACK_PLAYER_CLIENTS) if platform_type == PlatformType.YOUTUBE else [None]
                client_idx = 0

                for attempt in range(max_retries):
                    if attempt > 0:
                        backoff = (2 ** attempt) * 1.0
                        time.sleep(backoff)

                    logger = YtDlpQuietLogger()
                    item_ydl_opts: Dict[str, Any] = {
                        'format': self._get_format_string(quality, audio_only, allow_merge=has_ffmpeg, platform=platform_type),
                        'outtmpl': str(playlist_folder / f'{item_num:03d} - %(title)s.%(ext)s'),
                        'quiet': True,
                        'no_warnings': True,
                        'noprogress': True,
                        'noplaylist': True,
                        'logger': logger,
                        'progress_hooks': [playlist_progress.hook],
                        'postprocessor_hooks': [playlist_progress.postprocessor_hook],
                        'socket_timeout': 30,
                        'concurrent_fragment_downloads': 6,
                        'retries': 5,
                        'fragment_retries': 5,
                        'extractor_retries': 3,
                        'file_access_retries': 3,
                        'extractor_args': self._get_extractor_args(platform_type),
                        'http_headers': {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        },
                    }

                    if archive_active and self.archive_file:
                        item_ydl_opts['download_archive'] = str(self.archive_file)
                    if self.js_runtimes and platform_type == PlatformType.YOUTUBE:
                        item_ydl_opts['js_runtimes'] = self.js_runtimes
                    if has_ffmpeg and not audio_only:
                        item_ydl_opts['ffmpeg_location'] = shutil.which('ffmpeg')
                        item_ydl_opts['merge_output_format'] = 'mp4'

                    if audio_only:
                        if embed_thumbnail:
                            item_ydl_opts['writethumbnail'] = True
                        item_ydl_opts['postprocessors'] = self._get_audio_postprocessors(
                            audio_format=audio_format,
                            audio_quality=audio_quality,
                            embed_thumbnail=embed_thumbnail
                        )

                    if subtitles and not audio_only:
                        langs = [l.strip() for l in sub_lang.split(',') if l.strip()]
                        item_ydl_opts['writesubtitles'] = True
                        item_ydl_opts['writeautomaticsub'] = True
                        item_ydl_opts['subtitleslangs'] = langs if langs else ['es', 'en', 'es-419']
                        item_ydl_opts['subtitlesformat'] = 'srt/vtt/best'
                        if embed_subs and has_ffmpeg:
                            item_ydl_opts['embedsubtitles'] = True
                        if write_subs or not embed_subs:
                            if has_ffmpeg:
                                item_ydl_opts.setdefault('postprocessors', []).append({
                                    'key': 'FFmpegSubtitlesConvertor',
                                    'format': 'srt'
                                })

                    # Configurar cookies si se activaron para este elemento
                    if using_item_cookies:
                        item_cookie_opts = self._get_cookie_opts(
                            url=item_url,
                            cookies_from=curr_cookies_from or cookies_from,
                            cookies_file=curr_cookies_file or cookies_file
                        )
                        item_ydl_opts.update(item_cookie_opts)

                    # Configurar cliente rotativo si aplica
                    if curr_client and platform_type == PlatformType.YOUTUBE:
                        ext_args = dict(item_ydl_opts.get('extractor_args', {}))
                        yt_args = dict(ext_args.get('youtube', {}))
                        yt_args['player_client'] = [curr_client]
                        ext_args['youtube'] = yt_args
                        item_ydl_opts['extractor_args'] = ext_args

                    try:
                        with yt_dlp.YoutubeDL(item_ydl_opts) as item_ydl:
                            item_ydl.download([item_url])
                        item_success = True
                        item_reason = f"Completado ({time.time() - start_item_time:.1f}s)"
                        break
                    except Exception as ex:
                        err_str = str(ex)
                        err_lower = err_str.lower()
                        item_reason = err_str

                        # Si falló sin cookies, reintentar activando cookies si existen
                        if not using_item_cookies:
                            cand_cookies = self._get_cookie_opts(
                                url=item_url,
                                cookies_from=cookies_from,
                                cookies_file=cookies_file
                            )
                            if cand_cookies:
                                using_item_cookies = True
                                curr_cookies_from = cookies_from
                                curr_cookies_file = cookies_file
                                self.console.print(f"[dim cyan]ℹ️ Elemento #{item_num} sin cookies falló o requiere sesión. Reintentando con cookies...[/dim cyan]")
                                continue

                        is_403_or_bot = "403" in err_str or "forbidden" in err_lower or any(
                            k in err_lower for k in ("bot", "sign in", "confirm you", "n challenge", "potoken", "po_token", "rate-limit", "rate limit", "429")
                        )

                        # Intentar rotación de clientes si es YouTube y error 403
                        if is_403_or_bot and platform_type == PlatformType.YOUTUBE and client_idx < len(client_candidates) - 1:
                            client_idx += 1
                            curr_client = client_candidates[client_idx]
                            self.console.print(f"[dim cyan]ℹ️ Reintentando elemento #{item_num} con cliente YouTube: '{curr_client}'[/dim cyan]")
                            continue

                        # Si se agotó la rotación o no es YouTube, verificar recuperación interactiva
                        if is_403_or_bot and interactive and hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
                            recovery = prompt_interactive_recovery(
                                item_url,
                                failed_client=curr_client,
                                failed_cookie_source=curr_cookies_from or curr_cookies_file,
                                console_instance=self.console
                            )
                            if recovery:
                                if recovery.get('action') == 'retry_client':
                                    curr_client = recovery.get('client')
                                    continue
                                elif recovery.get('action') == 'retry_cookies_browser':
                                    curr_cookies_from = recovery.get('browser')
                                    continue
                                elif recovery.get('action') == 'retry_cookies_file':
                                    curr_cookies_file = recovery.get('file')
                                    continue
                                elif recovery.get('action') == 'retry_no_cookies':
                                    curr_cookies_from = None
                                    curr_cookies_file = None
                                    continue
                                elif recovery.get('action') == 'skip':
                                    item_skipped = True
                                    item_reason = "Omitido por el usuario"
                                    break
                                elif recovery.get('action') == 'abort':
                                    item_reason = "Abortado por el usuario"
                                    break

                        # Si es error transitorio y quedan intentos, continuar retroceso
                        is_transient = any(k in err_lower for k in ("timeout", "timed out", "connection reset", "connection refused", "502", "503", "504", "temporary"))
                        if is_transient and attempt < max_retries - 1:
                            continue

                # Registrar resultado del elemento
                if item_success:
                    status_str = "success"
                elif item_skipped:
                    status_str = "skipped"
                else:
                    status_str = "failed"

                results.append({
                    'index': item_num,
                    'title': item_title,
                    'status': status_str,
                    'reason': item_reason,
                    'url': item_url,
                })

                playlist_progress.advance_overall(item_num)

                # Si falló y abort_on_error está activo, detener la lista
                if status_str == "failed" and effective_abort:
                    self.console.print(f"[bold red]❌ Deteniendo lista tras fallo en elemento #{item_num} (abort-on-error activo).[/bold red]")
                    break
                if item_reason == "Abortado por el usuario":
                    break

            # =========================================================================
            # Renderizado de Tabla Rich de Auditoría Post-Ejecución
            # =========================================================================
            audit_table = Table(
                title=f"[bold cyan]📋 Resumen de Auditoría de Lista ({playlist_title})[/bold cyan]",
                header_style="bold magenta",
                border_style="cyan"
            )
            audit_table.add_column("#", style="dim", justify="center")
            audit_table.add_column("Título / Elemento", style="bold white", justify="left")
            audit_table.add_column("Estado", justify="center")
            audit_table.add_column("Detalles / Causa", justify="left")

            for r in results:
                short_title = r['title'] if len(r['title']) <= 45 else r['title'][:42] + "..."
                short_reason = r['reason'] if len(r['reason']) <= 50 else r['reason'][:47] + "..."
                if r['status'] == 'success':
                    audit_table.add_row(str(r['index']), short_title, "[bold green]✅ Éxito[/bold green]", f"[green]{short_reason}[/green]")
                elif r['status'] == 'skipped':
                    audit_table.add_row(str(r['index']), short_title, "[bold yellow]⚠️ Omitido[/bold yellow]", f"[yellow]{short_reason}[/yellow]")
                else:
                    audit_table.add_row(str(r['index']), short_title, "[bold red]❌ Fallido[/bold red]", f"[red]{short_reason}[/red]")

            self.console.print()
            self.console.print(audit_table)
            self.console.print()

            succeeded_count = sum(1 for r in results if r['status'] == 'success')
            failed_count = sum(1 for r in results if r['status'] == 'failed')
            skipped_count = sum(1 for r in results if r['status'] == 'skipped')
            total_processed = len(results)

            if succeeded_count > 0:
                summary_msg = f"✅ Guardados con éxito: {succeeded_count} de {total_videos} elementos."
                if failed_count > 0:
                    summary_msg += f"\n❌ Fallidos: {failed_count}"
                if skipped_count > 0:
                    summary_msg += f"\n⚠️ Omitidos: {skipped_count}"
                summary_msg += f"\n📁 Carpeta de destino: {playlist_folder}"
                print_success("¡Proceso de lista completado!", summary_msg, console_instance=self.console)
            else:
                print_error("Fallo en descarga de lista", f"No se pudo descargar ningún elemento ({failed_count} fallidos de {total_processed} intentados).", console_instance=self.console)

            # Notificación Windows Toast
            if notify:
                notif_title = get_notification_title(platform_type, audio_only=audio_only, is_playlist=True)
                show_desktop_notification(
                    notif_title,
                    f"{playlist_title}\nÉxito: {succeeded_count}/{total_videos} | Fallidos: {failed_count}",
                    playlist_folder
                )

            return succeeded_count > 0 or (total_processed > 0 and failed_count == 0)
            
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
        sleep_interval: Optional[float] = None,
        max_sleep_interval: Optional[float] = None,
        abort_on_error: bool = False,
        interactive: bool = False,
    ) -> bool:
        """
        Descarga múltiples medios desde un archivo de texto con URLs de cualquier plataforma soportando:
        - Concurrencia multihilo controlada (ThreadPoolExecutor) con --concurrency / -w
        - Control de pausas con jitter aleatorio inteligente (--sleep-interval, --max-sleep-interval o --delay)
        - Barras de progreso simultáneas en paralelo con Rich
        - Resumen de auditoría de lote
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

            effective_sleep = sleep_interval if sleep_interval is not None else delay
            pacing_label = f" • Pausa con jitter: {effective_sleep}s" if effective_sleep > 0 or max_sleep_interval else ""
            tipo_desc = f"Audio {audio_format.upper()} ({audio_quality} kbps)" if audio_only else f"Video {quality}p"
            subs_tag = f" • Subtítulos: {sub_lang}" if subtitles and not audio_only else ""
            
            self.console.print(Panel(
                f"[bold white]📋 Archivo de lote:[/bold white] [bold cyan]{file_path}[/bold cyan]\n"
                f"[bold white]📊 Total URLs a descargar:[/bold white] [yellow]{len(urls)}[/yellow]    "
                f"[bold white]⚡ Concurrencia:[/bold white] [green]{workers} workers simultáneos[/green]{pacing_label}\n"
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
                if item_idx > 1:
                    sleep_dur = calculate_pacing_delay(
                        sleep_interval=effective_sleep,
                        max_sleep_interval=max_sleep_interval,
                        default_pacing=(effective_sleep > 0)
                    )
                    if sleep_dur > 0:
                        time.sleep(sleep_dur)

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

                success = False
                err_msg = ""
                try:
                    # Fase 1: Descargar sin cookies
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    success = True
                except Exception as ex:
                    # Fase 2: Si falló sin cookies, intentar con sesión de cookies si están disponibles
                    batch_cookie_opts = self._get_cookie_opts(url=url, cookies_from=cookies_from, cookies_file=cookies_file)
                    if batch_cookie_opts:
                        ydl_opts_auth = dict(ydl_opts)
                        ydl_opts_auth.update(batch_cookie_opts)
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts_auth) as ydl_auth:
                                ydl_auth.download([url])
                            success = True
                            err_msg = ""
                        except Exception as ex_auth:
                            success = False
                            err_msg = str(ex_auth)
                    else:
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
