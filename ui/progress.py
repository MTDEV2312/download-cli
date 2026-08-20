"""
Módulo de gestores de barras de progreso con Rich para descargas individuales, playlists y lotes concurrentes.
Soporte universal para streams de video, audio, subtítulos y manifiestos HLS/DASH sin acoplamiento a YouTube.
"""

import re
import time
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from rich.console import Console, Group
from rich.table import Column
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)
from ui.console import console


class YtDlpQuietLogger:
    """Logger silencioso para yt-dlp para evitar que imprima texto sin formato sobre la UI de Rich"""
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def debug(self, msg: str):
        pass

    def info(self, msg: str):
        pass

    def warning(self, msg: str):
        self.warnings.append(msg)

    def error(self, msg: str):
        self.errors.append(msg)


def clean_stream_title(filename: str, info_dict: Optional[Dict[str, Any]] = None) -> str:
    """
    Limpia el título de archivo eliminando sufijos temporales de yt-dlp, itags y extensiones.
    """
    if info_dict and info_dict.get('title'):
        return info_dict['title']
    
    stem = Path(filename).stem
    # Eliminar extensiones temporales repetidas (.part, .temp, .ytdl, etc.) y sufijos de formato
    cleaned = re.sub(r'\.(f\d+|temp|part|ytdl|audio|video|frag\d+|mp4|webm|m4a|mp3|opus|mkv)$', '', stem, flags=re.IGNORECASE)
    cleaned = re.sub(r'\.(f\d+|temp|part|ytdl|audio|video|frag\d+)$', '', cleaned, flags=re.IGNORECASE)
    return cleaned or 'Descargando'


def classify_stream_label(
    filename: str,
    info_dict: Optional[Dict[str, Any]] = None,
    prefix: str = "",
    max_title_len: int = 28,
    console_instance: Optional[Console] = None
) -> str:
    """
    Clasifica de manera universal el tipo de stream que se está descargando
    (Audio, Video, Subtítulo o Stream HLS/DASH/Fragmentos) sin acoplamiento a itags de YouTube.
    Ajusta dinámicamente la longitud máxima del título según el ancho de la consola para evitar desbordamiento.
    """
    c = console_instance or console
    term_width = getattr(c, 'width', 80) or 80

    # Cálculo responsivo de longitud máxima de título según ancho de consola
    effective_max_len = max_title_len
    if term_width < 70:
        available = max(8, term_width - 32 - len(prefix))
        effective_max_len = min(max_title_len, available)
    elif term_width < 90:
        available = max(12, term_width - 42 - len(prefix))
        effective_max_len = min(max_title_len, available)
    elif term_width < 110:
        available = max(16, term_width - 50 - len(prefix))
        effective_max_len = min(max_title_len, available)

    title = clean_stream_title(filename, info_dict)
    if len(title) > effective_max_len:
        short_title = title[:max(1, effective_max_len - 3)] + "..."
    else:
        short_title = title

    file_name = Path(filename).name.lower()
    ext = Path(filename).suffix.lower()

    # 1. Subtítulos
    if any(file_name.endswith(sub_ext) for sub_ext in ('.vtt', '.srt', '.ttml', '.ass', '.sub', '.lrc', '.sbv')) or any(s in file_name for s in ('.sub.', '.subtitle.', '.subs.')):
        return f"📝 {prefix}Subtítulo: {short_title}"

    # 2. Streams de fragmentos / HLS / DASH
    if any(file_name.endswith(frag_ext) for frag_ext in ('.m3u8', '.mpd', '.ts', '.m4s')) or any(f in file_name for f in ('frag-', 'fragment-', 'chunk-', 'segment-', 'dash-', 'hls-')):
        return f"📡 {prefix}Stream: {short_title}"

    # 3. Pistas de audio
    is_audio = False
    if ext in ('.m4a', '.mp3', '.opus', '.flac', '.wav', '.aac', '.ogg', '.weba', '.wma', '.alac'):
        is_audio = True
    elif any(p in file_name for p in ('.audio.', '.ba.', '_audio.', '-audio.', 'audio_', '.f140.', '.f251.', '.f250.', '.f249.', '.f139.')):
        is_audio = True
    elif info_dict:
        vcodec = info_dict.get('vcodec')
        acodec = info_dict.get('acodec')
        if vcodec == 'none' and acodec and acodec != 'none':
            is_audio = True

    if is_audio:
        return f"🎵 {prefix}Audio: {short_title}"

    # 4. Pistas de video o streams combinados
    is_video = False
    if ext in ('.mp4', '.webm', '.mkv', '.mov', '.avi', '.flv', '.wmv', '.m4v'):
        is_video = True
    elif any(p in file_name for p in ('.video.', '.bv.', '_video.', '-video.', 'video_', '.f137.', '.f136.', '.f298.', '.f299.', '.f313.', '.f271.', '.f134.', '.f160.')):
        is_video = True
    elif info_dict:
        vcodec = info_dict.get('vcodec')
        if vcodec and vcodec != 'none':
            is_video = True

    if is_video:
        return f"🎬 {prefix}Video: {short_title}"

    # 5. Fallback genérico
    return f"⬇️  {prefix}{short_title}"


def get_postprocessor_label(pp: str, prefix: str = "") -> str:
    """Retorna un texto amigable para la fase de postprocesamiento de FFmpeg/yt-dlp"""
    pfx = f"{prefix} " if prefix else ""
    if 'ExtractAudio' in pp:
        return f"⚙️ {pfx}Extrayendo y convirtiendo audio..."
    elif 'Merger' in pp:
        return f"⚙️ {pfx}Combinando video y audio con FFmpeg..."
    elif 'EmbedThumbnail' in pp:
        return f"⚙️ {pfx}Incrustando carátula..."
    elif 'EmbedSubtitle' in pp:
        return f"⚙️ {pfx}Incrustando subtítulos en el video..."
    elif 'SubtitlesConvertor' in pp:
        return f"⚙️ {pfx}Convirtiendo subtítulos a formato SRT..."
    elif 'Metadata' in pp:
        return f"⚙️ {pfx}Escribiendo metadatos..."
    elif 'Fixup' in pp:
        return f"⚙️ {pfx}Corrigiendo contenedor multimedia..."
    elif 'Exec' in pp:
        return f"⚙️ {pfx}Ejecutando comando postprocesador..."
    else:
        return f"⚙️ {pfx}Procesando con FFmpeg ({pp})..."


class RichDownloadProgress:
    """Gestor de progreso de descarga individual con Rich"""
    def __init__(self, console_instance: Console = console, min_update_interval: float = 0.05):
        self.console = console_instance
        self.min_update_interval = min_update_interval
        self._last_update_time: float = 0.0
        self._last_size: Tuple[int, int] = (self.console.width, self.console.height)
        self.progress = Progress(
            SpinnerColumn(table_column=Column(no_wrap=True, overflow="crop")),
            TextColumn("[bold blue]{task.fields[filename]}", justify="left", table_column=Column(no_wrap=True, overflow="ellipsis")),
            BarColumn(bar_width=None, table_column=Column(ratio=1, no_wrap=True, overflow="crop")),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%", table_column=Column(no_wrap=True, overflow="crop")),
            DownloadColumn(table_column=Column(no_wrap=True, overflow="crop")),
            TransferSpeedColumn(table_column=Column(no_wrap=True, overflow="crop")),
            TimeRemainingColumn(table_column=Column(no_wrap=True, overflow="crop")),
            console=self.console,
            transient=False,
        )
        self.stream_task_id = None
        self.current_filename = None

    def _check_resize(self) -> bool:
        """Detecta cambios de dimensiones en la terminal y fuerza un refresco limpio."""
        try:
            current_size = (self.console.width, self.console.height)
            if current_size != self._last_size:
                self._last_size = current_size
                self.progress.refresh()
                return True
        except Exception:
            pass
        return False

    def hook(self, d: Dict[str, Any]):
        status = d.get('status')
        resized = self._check_resize()

        if status == 'downloading':
            filename = d.get('filename', '')
            info_dict = d.get('info_dict', {})
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)

            is_complete = (total is not None and downloaded is not None and total > 0 and downloaded >= total)
            is_first_update = (self.stream_task_id is None or self.current_filename != filename)
            now = time.time()

            # Throttling: evitar flood al terminal salvo primer evento, finalización, o cambio de tamaño
            if not is_first_update and not is_complete and not resized:
                if (now - self._last_update_time) < self.min_update_interval:
                    return

            self._last_update_time = now
            stream_name = classify_stream_label(filename, info_dict=info_dict, max_title_len=28, console_instance=self.console)

            if self.stream_task_id is None:
                self.stream_task_id = self.progress.add_task(
                    "download",
                    total=total,
                    completed=downloaded,
                    filename=stream_name
                )
                self.current_filename = filename
            elif self.current_filename != filename:
                self.progress.reset(
                    self.stream_task_id,
                    total=total,
                    completed=downloaded,
                    filename=stream_name
                )
                self.current_filename = filename
            else:
                self.progress.update(
                    self.stream_task_id,
                    completed=downloaded,
                    total=total,
                    filename=stream_name
                )

        elif status == 'finished':
            self._last_update_time = time.time()
            if self.stream_task_id is not None:
                total = d.get('total_bytes') or d.get('downloaded_bytes')
                if total:
                    self.progress.update(self.stream_task_id, completed=total, total=total)

    def postprocessor_hook(self, d: Dict[str, Any]):
        status = d.get('status')
        pp = d.get('postprocessor', '')
        if status == 'started':
            label = get_postprocessor_label(pp)
            if self.stream_task_id is not None:
                self.progress.update(self.stream_task_id, filename=f"[bold yellow]{label}[/bold yellow]")
        elif status == 'finished':
            if self.stream_task_id is not None:
                self.progress.update(self.stream_task_id, filename="[bold green]✓ Procesamiento completado[/bold green]")


class RichPlaylistProgress:
    """Gestor de progreso de doble barra para listas de reproducción"""
    def __init__(self, console_instance: Console = console, min_update_interval: float = 0.05):
        self.console = console_instance
        self.min_update_interval = min_update_interval
        self._last_update_time: float = 0.0
        self._last_size: Tuple[int, int] = (self.console.width, self.console.height)
        self.overall_progress = Progress(
            SpinnerColumn(table_column=Column(no_wrap=True, overflow="crop")),
            TextColumn("[bold magenta]{task.fields[filename]}", table_column=Column(no_wrap=True, overflow="ellipsis")),
            BarColumn(bar_width=None, table_column=Column(ratio=1, no_wrap=True, overflow="crop")),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%", table_column=Column(no_wrap=True, overflow="crop")),
            TextColumn("[dim]({task.completed}/{task.total} completados)[/dim]", table_column=Column(no_wrap=True, overflow="crop")),
            console=self.console,
        )
        self.file_progress = Progress(
            SpinnerColumn(table_column=Column(no_wrap=True, overflow="crop")),
            TextColumn("[bold blue]{task.fields[filename]}", justify="left", table_column=Column(no_wrap=True, overflow="ellipsis")),
            BarColumn(bar_width=None, table_column=Column(ratio=1, no_wrap=True, overflow="crop")),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%", table_column=Column(no_wrap=True, overflow="crop")),
            DownloadColumn(table_column=Column(no_wrap=True, overflow="crop")),
            TransferSpeedColumn(table_column=Column(no_wrap=True, overflow="crop")),
            TimeRemainingColumn(table_column=Column(no_wrap=True, overflow="crop")),
            console=self.console,
        )
        self.group = Group(self.overall_progress, self.file_progress)
        self.overall_task_id = None
        self.file_task_id = None
        self.current_filename = None
        self.current_index = 0
        self.total_count = 0
        self.title_prefix = "Playlist"

    def _check_resize(self) -> bool:
        """Detecta cambios de dimensiones en la terminal y fuerza un refresco limpio."""
        try:
            current_size = (self.console.width, self.console.height)
            if current_size != self._last_size:
                self._last_size = current_size
                self.overall_progress.refresh()
                self.file_progress.refresh()
                return True
        except Exception:
            pass
        return False

    def setup(self, total_items: int, title: str = "Playlist"):
        self.total_count = total_items
        self.title_prefix = title if len(title) <= 25 else title[:22] + "..."
        self.overall_task_id = self.overall_progress.add_task(
            "overall",
            total=total_items,
            completed=0,
            filename=f"📋 {self.title_prefix}"
        )
        self.file_task_id = self.file_progress.add_task(
            "file",
            total=None,
            completed=0,
            filename="Preparando descarga..."
        )

    def advance_overall(self, completed_count: int):
        self.current_index = completed_count
        if self.overall_task_id is not None:
            self.overall_progress.update(
                self.overall_task_id,
                completed=completed_count,
                filename=f"📋 {self.title_prefix}"
            )

    def hook(self, d: Dict[str, Any]):
        status = d.get('status')
        resized = self._check_resize()

        if status == 'downloading':
            filename = d.get('filename', '')
            info_dict = d.get('info_dict', {})
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)

            is_complete = (total is not None and downloaded is not None and total > 0 and downloaded >= total)
            is_first_update = (self.file_task_id is None or self.current_filename != filename)
            now = time.time()

            # Throttling
            if not is_first_update and not is_complete and not resized:
                if (now - self._last_update_time) < self.min_update_interval:
                    return

            self._last_update_time = now
            p_idx = info_dict.get('playlist_index') or self.current_index or '?'
            prefix = f"[{p_idx}/{self.total_count}] "
            stream_name = classify_stream_label(filename, info_dict=info_dict, prefix=prefix, max_title_len=20, console_instance=self.console)

            if self.file_task_id is None:
                self.file_task_id = self.file_progress.add_task(
                    "file",
                    total=total,
                    completed=downloaded,
                    filename=stream_name
                )
                self.current_filename = filename
            elif self.current_filename != filename:
                self.file_progress.reset(
                    self.file_task_id,
                    total=total,
                    completed=downloaded,
                    filename=stream_name
                )
                self.current_filename = filename
            else:
                self.file_progress.update(
                    self.file_task_id,
                    completed=downloaded,
                    total=total,
                    filename=stream_name
                )

        elif status == 'finished':
            self._last_update_time = time.time()
            if self.file_task_id is not None:
                total = d.get('total_bytes') or d.get('downloaded_bytes')
                if total:
                    self.file_progress.update(self.file_task_id, completed=total, total=total)

    def postprocessor_hook(self, d: Dict[str, Any]):
        status = d.get('status')
        pp = d.get('postprocessor', '')
        if status == 'started':
            label = get_postprocessor_label(pp)
            if self.file_task_id is not None:
                self.file_progress.update(self.file_task_id, filename=f"[bold yellow]{label}[/bold yellow]")


class RichConcurrentBatchProgress:
    """
    Gestor de progreso multihilo para descargas en lote (batch) concurrentes con Rich.
    Muestra una barra superior con el progreso global y barras activas para cada worker simultáneo.
    """
    def __init__(self, console_instance: Console = console, min_update_interval: float = 0.05):
        self.console = console_instance
        self.min_update_interval = min_update_interval
        self._last_size: Tuple[int, int] = (self.console.width, self.console.height)
        self.lock = threading.RLock()
        self.progress = Progress(
            SpinnerColumn(table_column=Column(no_wrap=True, overflow="crop")),
            TextColumn("[bold blue]{task.fields[filename]}", justify="left", table_column=Column(no_wrap=True, overflow="ellipsis")),
            BarColumn(bar_width=None, table_column=Column(ratio=1, no_wrap=True, overflow="crop")),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%", table_column=Column(no_wrap=True, overflow="crop")),
            DownloadColumn(table_column=Column(no_wrap=True, overflow="crop")),
            TransferSpeedColumn(table_column=Column(no_wrap=True, overflow="crop")),
            TimeRemainingColumn(table_column=Column(no_wrap=True, overflow="crop")),
            console=self.console,
            transient=False,
        )
        self.overall_task_id: Optional[int] = None
        self.total_items = 0

    def _check_resize(self) -> bool:
        """Detecta cambios de dimensiones en la terminal y fuerza un refresco limpio."""
        try:
            current_size = (self.console.width, self.console.height)
            if current_size != self._last_size:
                self._last_size = current_size
                self.progress.refresh()
                return True
        except Exception:
            pass
        return False

    def setup(self, total_items: int, title: str = "Descargas en Lote"):
        with self.lock:
            self.total_items = total_items
            self.overall_task_id = self.progress.add_task(
                "overall",
                total=total_items,
                completed=0,
                filename=f"[bold magenta]📋 {title} (0/{total_items} completados)[/bold magenta]"
            )

    def advance_overall(self, completed_count: int):
        with self.lock:
            if self.overall_task_id is not None:
                self.progress.update(
                    self.overall_task_id,
                    completed=completed_count,
                    filename=f"[bold magenta]📋 Progreso Global ({completed_count}/{self.total_items} completados)[/bold magenta]"
                )

    def create_hooks_for_item(self, item_idx: int, total_items: int, worker_id: int):
        """
        Retorna (progress_hook, postprocessor_hook, cleanup_callback) para una descarga en un hilo de trabajo.
        """
        task_id_box = [None]
        last_update_time = [0.0]

        def progress_hook(d: Dict[str, Any]):
            status = d.get('status')
            resized = self._check_resize()

            if status == 'downloading':
                filename = d.get('filename', '')
                info_dict = d.get('info_dict', {})
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded = d.get('downloaded_bytes', 0)

                is_complete = (total is not None and downloaded is not None and total > 0 and downloaded >= total)
                is_first_update = (task_id_box[0] is None)
                now = time.time()

                # Throttling por tarea / worker
                if not is_first_update and not is_complete and not resized:
                    if (now - last_update_time[0]) < self.min_update_interval:
                        return

                last_update_time[0] = now
                prefix = f"[W{worker_id}] [{item_idx}/{total_items}] "
                stream_name = classify_stream_label(filename, info_dict=info_dict, prefix=prefix, max_title_len=22, console_instance=self.console)

                with self.lock:
                    if task_id_box[0] is None:
                        task_id_box[0] = self.progress.add_task(
                            "download",
                            total=total,
                            completed=downloaded,
                            filename=stream_name
                        )
                    else:
                        self.progress.update(
                            task_id_box[0],
                            completed=downloaded,
                            total=total,
                            filename=stream_name
                        )
            elif status == 'finished':
                last_update_time[0] = time.time()
                with self.lock:
                    if task_id_box[0] is not None:
                        total = d.get('total_bytes') or d.get('downloaded_bytes')
                        if total:
                            self.progress.update(task_id_box[0], completed=total, total=total)

        def postprocessor_hook(d: Dict[str, Any]):
            status = d.get('status')
            pp = d.get('postprocessor', '')
            if status == 'started':
                prefix = f"[W{worker_id}] [{item_idx}/{total_items}]"
                label = get_postprocessor_label(pp, prefix=prefix)
                with self.lock:
                    if task_id_box[0] is not None:
                        self.progress.update(task_id_box[0], filename=f"[bold yellow]{label}[/bold yellow]")
            elif status == 'finished':
                with self.lock:
                    if task_id_box[0] is not None:
                        self.progress.update(task_id_box[0], filename=f"[bold green]✓ [W{worker_id}] [{item_idx}/{total_items}] Completado[/bold green]")

        def cleanup():
            with self.lock:
                if task_id_box[0] is not None:
                    try:
                        self.progress.remove_task(task_id_box[0])
                    except (KeyError, ValueError):
                        pass
                    task_id_box[0] = None

        return progress_hook, postprocessor_hook, cleanup
