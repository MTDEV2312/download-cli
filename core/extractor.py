"""
Módulo de extracción de metadatos, visualización de streams y selector interactivo universal de calidades.
Soporta YouTube, TikTok, Instagram, Twitter/X, Twitch, SoundCloud, Bandcamp, Vimeo, Kick, streams HLS/DASH y web genérica.
"""

import re
from typing import Optional, Dict, Any, List, Tuple
import yt_dlp
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from ui.console import console, handle_download_error
from ui.progress import YtDlpQuietLogger
from core.cookies import get_cookie_opts
from utils.formatters import (
    format_duration,
    format_bytes,
    format_views,
    format_date,
    clean_codec_name,
)
from utils.platform_detector import (
    PlatformType,
    PlatformInfo,
    detect_platform,
    get_platform_info,
)


def _apply_ytdlp_patches() -> None:
    """
    Aplica parches defensivos de compatibilidad sobre yt-dlp:
    - En sitios como ok.ru (Odnoklassniki), ciertos campos anidados (ej. flashvars['metadata'])
      pueden venir ya deserializados como dict/list en lugar de str, disparando TypeError en json.loads().
    - En Kick (kick.com), yt-dlp KickVODIE invoca 'api/v1/video/{id}' que fue deprecado por Kick (retorna 404).
      Se parchea KickVODIE para extraer directamente el stream HLS master ('recording_url')
      y metadatos desde el HTML server-side renderizado de Next.js.
    """
    from yt_dlp.extractor.common import InfoExtractor

    if not getattr(InfoExtractor._parse_json, "_is_defensive_patched", False):
        original_parse_json = InfoExtractor._parse_json

        def _safe_parse_json(
            self,
            json_string,
            video_id,
            transform_source=None,
            fatal=True,
            errnote=None,
            **parser_kwargs,
        ):
            if isinstance(json_string, (dict, list)):
                return json_string
            return original_parse_json(
                self,
                json_string,
                video_id,
                transform_source=transform_source,
                fatal=fatal,
                errnote=errnote,
                **parser_kwargs,
            )

        _safe_parse_json._is_defensive_patched = True  # type: ignore[attr-defined]
        InfoExtractor._parse_json = _safe_parse_json  # type: ignore[method-assign]

    try:
        from yt_dlp.extractor.kick import KickVODIE
        from yt_dlp.utils import ExtractorError, unified_timestamp

        if not getattr(KickVODIE, "_is_defensive_patched", False):
            orig_kick_vod_extract = KickVODIE._real_extract

            def _defensive_kick_vod_extract(self, url: str) -> Dict[str, Any]:
                video_id = self._match_id(url)

                # Descargar la página renderizada por el servidor Next.js de Kick
                webpage = self._download_webpage(url, video_id, note='Downloading Kick VOD webpage', fatal=False)
                if not webpage:
                    return orig_kick_vod_extract(self, url)

                # Extraer la URL del stream maestro HLS (AWS IVS)
                rec_match = re.search(r'recording_url["\\]*:\s*["\\]*(https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*)', webpage)
                stream_url = rec_match.group(1).replace(r'\/', '/') if rec_match else None

                is_sub_only = bool(re.search(r'status["\\]*:\s*["\\]*sub_only["\\]*', webpage))
                if not stream_url:
                    if is_sub_only:
                        raise ExtractorError(
                            f'El VOD {video_id} en Kick es exclusivo para suscriptores (sub_only). '
                            'Se requiere una sesión con suscripción activa al canal en cookies/cookies_kick.txt.',
                            expected=True
                        )
                    return orig_kick_vod_extract(self, url)

                formats = self._extract_m3u8_formats(stream_url, video_id, 'mp4')

                # Título
                title = None
                og_title_m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', webpage)
                if og_title_m:
                    title = og_title_m.group(1)
                else:
                    title_tag_m = re.search(r'<title>([^<]+)</title>', webpage)
                    if title_tag_m:
                        title = title_tag_m.group(1)
                if title:
                    title = re.sub(r'\s*-\s*[\w-]+\s+VOD\s+on\s+KICK\s*$', '', title, flags=re.IGNORECASE).strip()
                if not title:
                    title = f'Kick VOD {video_id}'

                # Descripción
                desc = None
                og_desc_m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', webpage)
                if og_desc_m:
                    desc = og_desc_m.group(1)

                # Miniatura
                thumbnail = None
                og_img_m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', webpage)
                if og_img_m:
                    thumbnail = og_img_m.group(1)

                # Creador / Canal
                uploader = None
                uploader_m = re.search(r'channel["\\]*:\s*\{[^}]*username["\\]*:\s*["\\]*([^"\\\\]+)', webpage)
                if uploader_m:
                    uploader = uploader_m.group(1)
                else:
                    url_m = re.search(r'kick\.com/([\w-]+)/videos/', url)
                    if url_m:
                        uploader = url_m.group(1)

                channel_id = None
                chan_id_m = re.search(r'channel["\\]*:\s*\{[^}]*id["\\]*:\s*([0-9]+)', webpage)
                if chan_id_m:
                    channel_id = chan_id_m.group(1)

                # Duración
                duration = None
                dur_m = re.search(r'["\\]*duration["\\]*:\s*([0-9]+)\s*,\s*["\\]*end_time', webpage)
                if dur_m:
                    val = int(dur_m.group(1))
                    duration = val if val < 100000 else val / 1000.0

                # Timestamp de emisión
                timestamp = None
                start_time_m = re.search(r'start_time["\\]*:\s*["\\]*([^"\\\\]+)', webpage)
                if start_time_m:
                    timestamp = unified_timestamp(start_time_m.group(1))

                return {
                    'id': video_id,
                    'title': title,
                    'description': desc,
                    'uploader': uploader,
                    'channel': uploader,
                    'uploader_id': channel_id,
                    'channel_id': channel_id,
                    'thumbnail': thumbnail,
                    'duration': duration,
                    'timestamp': timestamp,
                    'formats': formats,
                }

            _defensive_kick_vod_extract._is_defensive_patched = True  # type: ignore[attr-defined]
            KickVODIE._real_extract = _defensive_kick_vod_extract  # type: ignore[method-assign]
            KickVODIE._is_defensive_patched = True  # type: ignore[attr-defined]
    except Exception:
        pass


_apply_ytdlp_patches()



def _parse_format_dimensions(fmt: Dict[str, Any]) -> Tuple[int, int, int]:
    """
    Extrae de forma robusta (width, height, fps) de un formato de yt-dlp,
    soportando resoluciones en atributos de texto o format_notes (Twitch, HLS, etc.).
    """
    w = fmt.get('width') or 0
    h = fmt.get('height') or 0
    fps = fmt.get('fps') or 0
    
    if not h and fmt.get('resolution'):
        m = re.search(r'(\d+)x(\d+)', str(fmt.get('resolution')))
        if m:
            val1, val2 = int(m.group(1)), int(m.group(2))
            w = val1
            h = val2
            # Para videos verticales u horizontales, tomar la dimensión relevante
            if w < h and w > 0:
                h = max(val1, val2)
                
    if not h and fmt.get('format_note'):
        m = re.search(r'(\d+)p', str(fmt.get('format_note')), re.IGNORECASE)
        if m:
            h = int(m.group(1))

    if not h and fmt.get('format_id'):
        m = re.search(r'(\d+)p', str(fmt.get('format_id')), re.IGNORECASE)
        if m:
            h = int(m.group(1))

    if not fps and fmt.get('format_note'):
        m = re.search(r'p(\d+)', str(fmt.get('format_note')), re.IGNORECASE)
        if m:
            fps = int(m.group(1))

    return w, h, fps


# Clientes de reproducción YouTube para rotación automática y recuperación ante bloqueos 403 / antibot
FALLBACK_PLAYER_CLIENTS: List[str] = ['android', 'ios', 'mweb', 'tv_embedded', 'web']


def extract_info_with_client_fallback(
    url: str,
    base_ydl_opts: Dict[str, Any],
    candidate_clients: Optional[List[str]] = None,
    console_instance: Optional[Console] = None,
    suppress_error_log: bool = False
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Intenta la extracción de metadatos iterando a través de clientes de reproducción candidatos
    cuando se encuentran errores HTTP 403 Forbidden, desafíos antibot o restricciones de poToken en YouTube.
    Retorna (info_dict, cliente_exitoso) o (None, None) en caso de fallo.
    """
    c = console_instance or console
    platform_type, _, _ = detect_platform(url)

    if platform_type != PlatformType.YOUTUBE:
        try:
            with yt_dlp.YoutubeDL(base_ydl_opts) as ydl:
                return (ydl.extract_info(url, download=False), None)
        except Exception as e:
            if not suppress_error_log:
                handle_download_error(e, url, console_instance=c)
            return (None, None)

    clients = list(candidate_clients or FALLBACK_PLAYER_CLIENTS)
    last_error: Optional[Exception] = None

    for idx, client in enumerate(clients):
        ydl_opts = dict(base_ydl_opts)
        ext_args = dict(ydl_opts.get('extractor_args', {}))
        yt_args = dict(ext_args.get('youtube', {}))
        yt_args['player_client'] = [client]
        ext_args['youtube'] = yt_args
        ydl_opts['extractor_args'] = ext_args

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is not None:
                    if idx > 0:
                        c.print(f"[dim cyan]ℹ️ Extracción recuperada con éxito usando cliente YouTube: '{client}'[/dim cyan]")
                    return (info, client)
        except Exception as e:
            last_error = e
            err_lower = str(e).lower()
            is_403_or_bot = "403" in str(e) or "forbidden" in err_lower or any(
                k in err_lower for k in ("bot", "sign in", "confirm you", "n challenge", "potoken", "po_token", "rate-limit", "rate limit", "429")
            )
            # Si hay más clientes y el error es susceptible de rotación, continuar
            if idx < len(clients) - 1 and is_403_or_bot:
                continue
            elif idx == len(clients) - 1:
                # Todos los clientes candidatos agotados
                break

    if last_error and not suppress_error_log:
        handle_download_error(last_error, url, console_instance=c)
    return (None, None)


def get_raw_info(
    url: str,
    js_runtimes: Optional[Dict[str, Any]] = None,
    cookies_from: Optional[str] = None,
    cookies_file: Optional[str] = None,
    default_cookies_from: Optional[str] = None,
    default_cookies_file: Optional[str] = None,
    console_instance: Optional[Console] = None
) -> Optional[Dict[str, Any]]:
    """
    Obtiene la información cruda completa de yt-dlp sin descargar para cualquier plataforma.
    Implementa estrategia de 2 fases: primero intenta sin cookies; si falla, reintenta con cookies.
    """
    c = console_instance or console
    try:
        platform_type, _, _ = detect_platform(url)
        logger = YtDlpQuietLogger()
        
        extractor_args: Dict[str, Any] = {}
        if platform_type == PlatformType.YOUTUBE:
            extractor_args['youtube'] = {'player_client': ['android', 'web', 'tv']}
        elif platform_type == PlatformType.TIKTOK:
            extractor_args['tiktok'] = {'app_version': 'latest'}

        base_ydl_opts: Dict[str, Any] = {
            'quiet': True,
            'noplaylist': True,
            'no_warnings': True,
            'logger': logger,
            'extractor_args': extractor_args,
        }
        if js_runtimes and platform_type == PlatformType.YOUTUBE:
            base_ydl_opts['js_runtimes'] = js_runtimes

        # Fase 1: Intento sin cookies (sesión limpia)
        info_clean, _ = extract_info_with_client_fallback(
            url,
            base_ydl_opts=base_ydl_opts,
            console_instance=c,
            suppress_error_log=True
        )
        if info_clean is not None:
            info_clean['_used_cookies'] = False
            return info_clean

        # Fase 2: Si falló sin cookies, resolver si hay cookies disponibles para fallback
        cookie_opts = get_cookie_opts(
            url=url,
            cookies_from=cookies_from,
            cookies_file=cookies_file,
            default_cookies_from=default_cookies_from,
            default_cookies_file=default_cookies_file
        )

        if cookie_opts:
            c.print("[dim cyan]ℹ️ Extracción sin cookies falló o requiere sesión. Reintentando con cookies...[/dim cyan]")
            ydl_opts_cookies = dict(base_ydl_opts)
            ydl_opts_cookies.update(cookie_opts)
            info_cookies, _ = extract_info_with_client_fallback(
                url,
                base_ydl_opts=ydl_opts_cookies,
                console_instance=c,
                suppress_error_log=False
            )
            if info_cookies is not None:
                info_cookies['_used_cookies'] = True
                info_cookies['_cookie_opts'] = cookie_opts
                return info_cookies
            return None

        # Si no había cookies disponibles, reejecutar Fase 1 para emitir diagnóstico visual de error
        extract_info_with_client_fallback(
            url,
            base_ydl_opts=base_ydl_opts,
            console_instance=c,
            suppress_error_log=False
        )
        return None
    except Exception as e:
        handle_download_error(e, url, console_instance=c)
        return None


def get_video_info(
    url: str,
    js_runtimes: Optional[Dict[str, Any]] = None,
    cookies_from: Optional[str] = None,
    cookies_file: Optional[str] = None,
    default_cookies_from: Optional[str] = None,
    default_cookies_file: Optional[str] = None,
    console_instance: Optional[Console] = None
) -> Optional[Dict[str, Any]]:
    """Obtiene información estructurada y formatos del video o medio"""
    info = get_raw_info(
        url,
        js_runtimes=js_runtimes,
        cookies_from=cookies_from,
        cookies_file=cookies_file,
        default_cookies_from=default_cookies_from,
        default_cookies_file=default_cookies_file,
        console_instance=console_instance
    )
    if not info:
        return None
    if 'entries' in info and info['entries']:
        info = info['entries'][0]
        
    platform_type, platform_name, badge_rich = detect_platform(url)
    formats = info.get('formats', [])
    is_audio_only = all(f.get('vcodec') == 'none' for f in formats) if formats else False

    return {
        'id': info.get('id', ''),
        'title': info.get('title', 'Desconocido'),
        'uploader': info.get('uploader') or info.get('channel') or info.get('artist') or info.get('creator') or 'Desconocido',
        'duration': info.get('duration', 0),
        'view_count': info.get('view_count'),
        'like_count': info.get('like_count'),
        'upload_date': info.get('upload_date'),
        'description': info.get('description', ''),
        'thumbnail': info.get('thumbnail', ''),
        'formats': formats,
        'subtitles': info.get('subtitles', {}),
        'automatic_captions': info.get('automatic_captions', {}),
        'webpage_url': info.get('webpage_url', url),
        'platform': platform_type,
        'platform_name': platform_name,
        'platform_badge': badge_rich,
        'is_audio_only': is_audio_only,
        '_raw_info': info,
    }


# Alias universal
get_media_info = get_video_info


def display_info(
    url: str,
    js_runtimes: Optional[Dict[str, Any]] = None,
    cookies_from: Optional[str] = None,
    cookies_file: Optional[str] = None,
    default_cookies_from: Optional[str] = None,
    default_cookies_file: Optional[str] = None,
    console_instance: Optional[Console] = None
) -> None:
    """Muestra un panel visual con metadatos del medio y una tabla con los formatos y subtítulos disponibles"""
    c = console_instance or console
    platform_type, platform_name, badge_rich = detect_platform(url)
    
    with c.status(f"[bold cyan]🔍 Consultando metadatos y formatos de {platform_name}...", spinner="dots"):
        info_data = get_video_info(
            url,
            js_runtimes=js_runtimes,
            cookies_from=cookies_from,
            cookies_file=cookies_file,
            default_cookies_from=default_cookies_from,
            default_cookies_file=default_cookies_file,
            console_instance=c
        )

    if not info_data:
        return

    # 1. Panel de Metadatos
    meta_text = (
        f"[bold white]🌐 Plataforma:[/bold white] {info_data['platform_badge']}\n"
        f"[bold white]📺 Título:[/bold white] [bold cyan]{info_data['title']}[/bold cyan]\n"
        f"[bold white]👤 Autor / Canal:[/bold white] [yellow]{info_data['uploader']}[/yellow]    "
        f"[bold white]⏱️  Duración:[/bold white] [green]{format_duration(info_data['duration'])}[/green]    "
        f"[bold white]👁️  Vistas:[/bold white] [blue]{format_views(info_data['view_count'])}[/blue]\n"
        f"[bold white]📅 Publicado:[/bold white] [magenta]{format_date(info_data['upload_date'])}[/magenta]    "
        f"[bold white]🆔 ID:[/bold white] [dim]{info_data['id']}[/dim]    "
        f"[bold white]🔗 URL:[/bold white] [dim]{info_data['webpage_url']}[/dim]"
    )
    c.print(Panel(meta_text, title=f"[bold cyan]🎬 Información de Medios - {info_data['platform_name']}[/bold cyan]", border_style="cyan", expand=False))

    # 2. Subtítulos Disponibles (si aplica)
    subs_manual = list(info_data.get('subtitles', {}).keys())
    subs_auto = list(info_data.get('automatic_captions', {}).keys())
    
    if subs_manual or subs_auto:
        subs_parts = []
        if subs_manual:
            subs_parts.append(f"[bold green]Manuales:[/bold green] {', '.join(subs_manual[:8])}{'...' if len(subs_manual)>8 else ''}")
        if subs_auto:
            subs_parts.append(f"[bold yellow]Autogenerados:[/bold yellow] {', '.join(subs_auto[:8])}{'...' if len(subs_auto)>8 else ''}")
            
        subs_str = " | ".join(subs_parts)
        c.print(Panel(f"📝 {subs_str}", title="[bold cyan]Subtítulos Disponibles[/bold cyan]", border_style="dim cyan", expand=False))

    # 3. Tabla de Formatos y Streams
    formats = info_data.get('formats', [])
    if not formats:
        c.print("[dim]No se encontraron streams específicos para este enlace.[/dim]")
        return

    table = Table(
        title=f"[bold cyan]📹 Formatos y Streams Disponibles ({info_data['platform_name']})[/bold cyan]",
        header_style="bold magenta",
        border_style="cyan",
        show_lines=False
    )
    table.add_column("ID", style="dim", justify="center")
    table.add_column("Tipo", justify="center")
    table.add_column("Resolución / Calidad", style="bold green", justify="left")
    table.add_column("FPS", justify="center")
    table.add_column("Códec Video", style="cyan", justify="left")
    table.add_column("Códec Audio", style="yellow", justify="left")
    table.add_column("Bitrate", justify="right")
    table.add_column("Tamaño Est.", style="bold white", justify="right")
    table.add_column("Ext", justify="center")

    # Clasificar y agrupar formatos
    video_streams: Dict[int, Dict[str, Any]] = {}
    audio_streams: List[Dict[str, Any]] = []
    prog_streams: List[Dict[str, Any]] = []

    for fmt in formats:
        if fmt.get('format_note') == 'storyboard' or fmt.get('ext') == 'mhtml':
            continue
        vcodec = fmt.get('vcodec', 'none')
        acodec = fmt.get('acodec', 'none')
        w, h, fps = _parse_format_dimensions(fmt)
        
        if vcodec != 'none' and acodec != 'none' and h > 0:
            prog_streams.append((fmt, w, h, fps))
        elif vcodec != 'none' and h > 0:
            key = h * 1000 + int(fps)
            current_br = fmt.get('vbr') or fmt.get('tbr') or 0
            if key not in video_streams or (video_streams[key][0].get('vbr') or 0) < current_br:
                video_streams[key] = (fmt, w, h, fps)
        elif acodec != 'none':
            audio_streams.append(fmt)

    # Streams de video separados
    sorted_videos = [video_streams[k] for k in sorted(video_streams.keys(), reverse=True)]
    for fmt, w, h, fps in sorted_videos:
        fps_str = f"{fps}fps" if fps else "-"
        res_label = f"{h}p"
        if h >= 2160: res_label += " (4K Ultra HD)"
        elif h >= 1440: res_label += " (2K QHD)"
        elif h >= 1080: res_label += " (Full HD)"
        elif h >= 720: res_label += " (HD)"

        br = fmt.get('vbr') or fmt.get('tbr')
        br_str = f"{br:.0f} kbps" if br else "-"
        size_val = fmt.get('filesize') or fmt.get('filesize_approx')
        size_str = format_bytes(size_val)

        table.add_row(
            str(fmt.get('format_id', '')),
            "[blue]Video[/blue]",
            f"{w}x{h} ({res_label})" if w else res_label,
            fps_str,
            clean_codec_name(fmt.get('vcodec')),
            "-",
            br_str,
            size_str,
            str(fmt.get('ext', ''))
        )

    # Streams progresivos directos (TikTok, Twitter, Instagram, etc.)
    for fmt, w, h, fps in prog_streams:
        br = fmt.get('tbr') or fmt.get('vbr') or 0
        br_str = f"{br:.0f} kbps" if br else "-"
        size_val = fmt.get('filesize') or fmt.get('filesize_approx')
        res_text = f"{w}x{h} ({h}p)" if w else f"{h}p (Directo)"
        table.add_row(
            str(fmt.get('format_id', '')),
            "[green]Video+Audio[/green]",
            res_text,
            f"{fps}fps" if fps else "30fps",
            clean_codec_name(fmt.get('vcodec')),
            clean_codec_name(fmt.get('acodec')),
            br_str,
            format_bytes(size_val),
            str(fmt.get('ext', ''))
        )

    # Streams de audio
    audio_streams.sort(key=lambda x: (x.get('abr') or x.get('tbr') or 0), reverse=True)
    for fmt in audio_streams[:5]:
        abr = fmt.get('abr') or fmt.get('tbr')
        abr_str = f"{abr:.0f} kbps" if abr else "-"
        size_val = fmt.get('filesize') or fmt.get('filesize_approx')
        codec_label = clean_codec_name(fmt.get('acodec'))
        quality_label = f"Audio HQ ({codec_label})" if (abr or 0) >= 128 else f"Audio ({codec_label})"

        table.add_row(
            str(fmt.get('format_id', '')),
            "[magenta]Audio[/magenta]",
            quality_label,
            "-",
            "-",
            codec_label,
            abr_str,
            format_bytes(size_val),
            str(fmt.get('ext', ''))
        )

    c.print(table)


def interactive_select_format(
    url: str,
    downloader_instance: Optional[Any] = None,
    js_runtimes: Optional[Dict[str, Any]] = None,
    cookies_from: Optional[str] = None,
    cookies_file: Optional[str] = None,
    default_cookies_from: Optional[str] = None,
    default_cookies_file: Optional[str] = None,
    console_instance: Optional[Console] = None
) -> Optional[Dict[str, Any]]:
    """
    Analiza los formatos disponibles en cualquier plataforma (YouTube, TikTok, Instagram,
    Twitter/X, Twitch, SoundCloud, Bandcamp, etc.) y ofrece un selector visual interactivo adaptativo.
    """
    c = console_instance or console
    platform_type, platform_name, badge_rich = detect_platform(url)

    with c.status(f"[bold cyan]🔍 Analizando resoluciones y formatos de {platform_name}...", spinner="dots"):
        if downloader_instance and hasattr(downloader_instance, 'get_raw_info'):
            info_data = downloader_instance.get_raw_info(url, cookies_from=cookies_from, cookies_file=cookies_file)
        else:
            info_data = get_raw_info(
                url,
                js_runtimes=js_runtimes,
                cookies_from=cookies_from,
                cookies_file=cookies_file,
                default_cookies_from=default_cookies_from,
                default_cookies_file=default_cookies_file,
                console_instance=c
            )

    if not info_data:
        return None

    entry = info_data['entries'][0] if 'entries' in info_data and info_data['entries'] else info_data
    title = entry.get('title', 'Desconocido')
    duration = entry.get('duration', 0)
    uploader = entry.get('uploader') or entry.get('channel') or entry.get('artist') or entry.get('creator') or 'Desconocido'
    formats = entry.get('formats', [])

    # Mostrar panel informativo
    c.print(Panel(
        f"[bold white]🌐 Plataforma:[/bold white] {badge_rich}\n"
        f"[bold white]📺 Título:[/bold white] [bold cyan]{title}[/bold cyan]\n"
        f"[bold white]👤 Autor / Canal:[/bold white] [yellow]{uploader}[/yellow]    "
        f"[bold white]⏱️  Duración:[/bold white] [green]{format_duration(duration)}[/green]",
        title=f"[bold cyan]🎬 Selector Interactivo de Calidad - {platform_name}[/bold cyan]",
        border_style="cyan",
        expand=False
    ))

    # Comprobar si el contenido es solo de audio (SoundCloud, Bandcamp o sin streams de video)
    has_video = any(fmt.get('vcodec') != 'none' for fmt in formats) if formats else False
    is_pure_audio = (not has_video) or platform_type in (PlatformType.SOUNDCLOUD, PlatformType.BANDCAMP) and not has_video

    if is_pure_audio:
        c.print(Panel(
            f"[bold magenta]🎵 Contenido identificado como pista de audio ({platform_name}).[/bold magenta]\n"
            f"[dim]No requiere selección de video. Elige formato y calidad de audio a continuación.[/dim]",
            title=f"[bold cyan]🎧 Modo Solo Audio ({platform_name})[/bold cyan]",
            border_style="magenta",
            expand=False
        ))
        
        c.print("\n[bold cyan]Formatos de audio disponibles:[/bold cyan]")
        c.print("  [bold yellow]1[/bold yellow] - MP3  (320 kbps / Máxima compatibilidad)")
        c.print("  [bold yellow]2[/bold yellow] - FLAC (Sin pérdida / Lossless)")
        c.print("  [bold yellow]3[/bold yellow] - M4A  (AAC de alta fidelidad)")
        c.print("  [bold yellow]4[/bold yellow] - OPUS (Mayor compresión y calidad moderna)")
        c.print("  [bold yellow]5[/bold yellow] - WAV  (Sin comprimir)")
        
        afmt_choice = Prompt.ask("[bold green]?[/bold green] Elige formato de audio", default="1", console=c).strip()
        afmt_map = {"1": "mp3", "2": "flac", "3": "m4a", "4": "opus", "5": "wav"}
        audio_format = afmt_map.get(afmt_choice, "mp3")

        audio_quality = "320"
        if audio_format == "mp3":
            c.print("\n[bold cyan]Bitrate para MP3:[/bold cyan]")
            c.print("  [bold yellow]1[/bold yellow] - 320 kbps (Máxima calidad)")
            c.print("  [bold yellow]2[/bold yellow] - 256 kbps (Muy alta calidad)")
            c.print("  [bold yellow]3[/bold yellow] - 192 kbps (Calidad estándar)")
            c.print("  [bold yellow]4[/bold yellow] - 128 kbps (Ahorro de espacio)")
            aq_choice = Prompt.ask("[bold green]?[/bold green] Elige bitrate", default="1", console=c).strip()
            aq_map = {"1": "320", "2": "256", "3": "192", "4": "128"}
            audio_quality = aq_map.get(aq_choice, "320")

        return {
            'quality': 'best',
            'audio_only': True,
            'audio_format': audio_format,
            'audio_quality': audio_quality,
            'subtitles': False,
            'sub_lang': 'es,en,es-419',
            'embed_subs': False,
            'write_subs': False,
            'info_dict': info_data,
        }

    # Identificar el tamaño estimado del mejor audio
    best_audio_size = 0
    best_audio_br = 0
    for fmt in formats:
        if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
            br = fmt.get('abr') or fmt.get('tbr') or 0
            if br > best_audio_br:
                best_audio_br = br
                best_audio_size = fmt.get('filesize') or fmt.get('filesize_approx') or 0

    # Agrupar streams de video por resolución
    video_map: Dict[str, Dict[str, Any]] = {}
    
    for fmt in formats:
        if fmt.get('format_note') == 'storyboard' or fmt.get('ext') == 'mhtml':
            continue
        if fmt.get('vcodec') == 'none':
            continue

        w, h, fps = _parse_format_dimensions(fmt)
        if h <= 0:
            continue

        fps = fps or 30
        is_60 = fps >= 50
        
        # Etiqueta de resolución
        if h >= 4320:
            res_key = "4320"
            label = "8K Ultra HD (4320p)"
        elif h >= 2160:
            res_key = "2160"
            label = "4K Ultra HD (2160p" + ("60" if is_60 else "") + ")"
        elif h >= 1440:
            res_key = "1440"
            label = "2K QHD (1440p" + ("60" if is_60 else "") + ")"
        elif h >= 1080:
            res_key = "1080_60" if is_60 else "1080"
            label = "Full HD (1080p60)" if is_60 else "Full HD (1080p)"
        elif h >= 720:
            res_key = "720_60" if is_60 else "720"
            label = "HD (720p60)" if is_60 else "HD (720p)"
        elif h >= 480:
            res_key = "480"
            label = "SD (480p)"
        elif h >= 360:
            res_key = "360"
            label = "SD (360p)"
        else:
            res_key = f"{h}"
            label = f"Baja ({h}p)"

        vbr = fmt.get('vbr') or fmt.get('tbr') or 0
        v_size = fmt.get('filesize') or fmt.get('filesize_approx') or 0
        total_size = v_size + (best_audio_size if fmt.get('acodec') == 'none' else 0)

        if res_key not in video_map or (video_map[res_key].get('vbr', 0) < vbr):
            video_map[res_key] = {
                'height': str(h),
                'label': label,
                'fps': fps,
                'vcodec': clean_codec_name(fmt.get('vcodec')),
                'vbr': vbr,
                'estimated_size': total_size,
                'sort_val': h * 1000 + int(fps)
            }

    # Ordenar resoluciones descendente
    sorted_resolutions = sorted(video_map.values(), key=lambda x: x['sort_val'], reverse=True)

    # Construir tabla visual de opciones
    table = Table(
        title=f"[bold green]Opciones de Calidad Disponibles ({platform_name})[/bold green]",
        header_style="bold magenta",
        border_style="green",
        show_lines=False
    )
    table.add_column("Opción", style="bold yellow", justify="center")
    table.add_column("Resolución / Tipo", style="bold white", justify="left")
    table.add_column("FPS", justify="center")
    table.add_column("Códec", style="cyan", justify="left")
    table.add_column("Tamaño Est.", style="green", justify="right")

    # Opción 0: Mejor disponible (automático)
    table.add_row(
        "0",
        "⭐ [bold cyan]Mejor calidad disponible (Automático)[/bold cyan]",
        "-",
        "Óptimo",
        "-"
    )

    # Opciones de video detectadas
    option_lookup: Dict[str, Dict[str, Any]] = {}
    for idx, opt in enumerate(sorted_resolutions, 1):
        opt_key = str(idx)
        option_lookup[opt_key] = opt
        size_str = format_bytes(opt['estimated_size']) if opt['estimated_size'] > 0 else "-"
        table.add_row(
            opt_key,
            f"🎬 {opt['label']}",
            f"{opt['fps']}fps",
            opt['vcodec'],
            size_str
        )

    # Opciones especiales de audio y cancelación
    table.add_row("A", "🎵 [bold magenta]Solo Audio (MP3 320k, FLAC, M4A, OPUS, WAV)[/bold magenta]", "-", "Varios", "-")
    table.add_row("C", "[red]❌ Cancelar descarga[/red]", "-", "-", "-")

    c.print(table)
    c.print()

    # Solicitar selección al usuario
    choice = Prompt.ask(
        "[bold green]?[/bold green] Selecciona una opción de calidad",
        default="0",
        console=c
    ).strip().upper()

    if choice == "C":
        c.print("[yellow]Operación cancelada por el usuario.[/yellow]")
        return None

    selected_quality = "best"
    audio_only = False
    audio_format = "mp3"
    audio_quality = "320"
    subtitles = False
    sub_lang = "es,en,es-419"

    if choice == "A":
        audio_only = True
        c.print("\n[bold cyan]Formatos de audio disponibles:[/bold cyan]")
        c.print("  [bold yellow]1[/bold yellow] - MP3  (320 kbps / Máxima compatibilidad)")
        c.print("  [bold yellow]2[/bold yellow] - FLAC (Sin pérdida / Lossless)")
        c.print("  [bold yellow]3[/bold yellow] - M4A  (AAC de alta fidelidad)")
        c.print("  [bold yellow]4[/bold yellow] - OPUS (Mayor compresión y calidad moderna)")
        c.print("  [bold yellow]5[/bold yellow] - WAV  (Sin comprimir)")
        
        afmt_choice = Prompt.ask("[bold green]?[/bold green] Elige formato de audio", default="1", console=c).strip()
        afmt_map = {"1": "mp3", "2": "flac", "3": "m4a", "4": "opus", "5": "wav"}
        audio_format = afmt_map.get(afmt_choice, "mp3")

        if audio_format == "mp3":
            c.print("\n[bold cyan]Bitrate para MP3:[/bold cyan]")
            c.print("  [bold yellow]1[/bold yellow] - 320 kbps (Máxima calidad)")
            c.print("  [bold yellow]2[/bold yellow] - 256 kbps (Muy alta calidad)")
            c.print("  [bold yellow]3[/bold yellow] - 192 kbps (Calidad estándar)")
            c.print("  [bold yellow]4[/bold yellow] - 128 kbps (Ahorro de espacio)")
            aq_choice = Prompt.ask("[bold green]?[/bold green] Elige bitrate", default="1", console=c).strip()
            aq_map = {"1": "320", "2": "256", "3": "192", "4": "128"}
            audio_quality = aq_map.get(aq_choice, "320")

    elif choice in option_lookup:
        selected_quality = option_lookup[choice]['height']
    elif choice == "0":
        selected_quality = "best"
    else:
        c.print(f"[yellow]Opción '{choice}' no reconocida. Usando mejor calidad disponible.[/yellow]")
        selected_quality = "best"

    # Preguntar si se desean subtítulos (solo para videos)
    if not audio_only:
        want_subs = Confirm.ask("\n[bold green]?[/bold green] ¿Deseas descargar e incrustar subtítulos en el video?", default=False, console=c)
        if want_subs:
            subtitles = True
            sub_lang = Prompt.ask("[bold green]?[/bold green] Idiomas de subtítulos (separados por coma)", default="es,en,es-419", console=c).strip()

    return {
        'quality': selected_quality,
        'audio_only': audio_only,
        'audio_format': audio_format,
        'audio_quality': audio_quality,
        'subtitles': subtitles,
        'sub_lang': sub_lang,
        'embed_subs': True,
        'write_subs': False,
        'info_dict': info_data,
    }
