"""
Módulo de gestión, configuración y diagnóstico multi-sitio de cookies y sesiones.
Soporta YouTube, TikTok, Instagram, Twitter/X, Twitch, Facebook, Reddit, SoundCloud, Bandcamp y más.
Implementa búsqueda en cascada inteligente en carpeta cookies/ y auditoría de sesiones en navegadores.
"""

import os
import io
import sys
import shutil
import tempfile
import contextlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Set

import yt_dlp
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ui.console import console
from utils.formatters import format_bytes
from utils.platform_detector import (
    PlatformType,
    PlatformInfo,
    detect_platform,
    get_platform_info,
)

# Carpeta dedicada para almacenamiento seguro y ordenado de cookies locales
COOKIES_DIR: Path = Path("cookies")

# Navegadores web soportados por yt-dlp para extracción directa de cookies
SUPPORTED_BROWSERS: List[str] = ['brave', 'chrome', 'edge', 'firefox', 'opera', 'vivaldi']
if sys.platform == 'darwin':
    SUPPORTED_BROWSERS.append('safari')

# Mapeo de plataformas a nombres legibles y dominios clave para auditoría en navegadores
PLATFORM_COOKIE_DOMAINS: Dict[PlatformType, Tuple[str, List[str]]] = {
    PlatformType.YOUTUBE: ("YouTube", ["youtube.com", "google.com", "googlevideo.com", "youtu.be"]),
    PlatformType.INSTAGRAM: ("Instagram", ["instagram.com", "instagr.am"]),
    PlatformType.TIKTOK: ("TikTok", ["tiktok.com"]),
    PlatformType.TWITTER: ("Twitter / X", ["twitter.com", "x.com", "t.co"]),
    PlatformType.TWITCH: ("Twitch", ["twitch.tv"]),
    PlatformType.FACEBOOK: ("Facebook", ["facebook.com", "fb.com", "fb.watch"]),
    PlatformType.REDDIT: ("Reddit", ["reddit.com", "redd.it"]),
    PlatformType.SOUNDCLOUD: ("SoundCloud", ["soundcloud.com"]),
    PlatformType.BANDCAMP: ("Bandcamp", ["bandcamp.com"]),
    PlatformType.VIMEO: ("Vimeo", ["vimeo.com"]),
}

# Nombres de archivos de cookies estándar asociados a cada plataforma
PLATFORM_COOKIE_FILES: Dict[PlatformType, List[str]] = {
    PlatformType.YOUTUBE: ["cookies_youtube.txt", "youtube_cookies.txt"],
    PlatformType.INSTAGRAM: ["cookies_instagram.txt", "instagram_cookies.txt"],
    PlatformType.TIKTOK: ["cookies_tiktok.txt", "tiktok_cookies.txt"],
    PlatformType.TWITTER: ["cookies_twitter.txt", "twitter_cookies.txt", "cookies_x.txt", "x_cookies.txt"],
    PlatformType.TWITCH: ["cookies_twitch.txt", "twitch_cookies.txt"],
    PlatformType.FACEBOOK: ["cookies_facebook.txt", "facebook_cookies.txt"],
    PlatformType.REDDIT: ["cookies_reddit.txt", "reddit_cookies.txt"],
    PlatformType.SOUNDCLOUD: ["cookies_soundcloud.txt", "soundcloud_cookies.txt"],
    PlatformType.BANDCAMP: ["cookies_bandcamp.txt", "bandcamp_cookies.txt"],
    PlatformType.VIMEO: ["cookies_vimeo.txt", "vimeo_cookies.txt"],
    PlatformType.KICK: ["cookies_kick.txt", "kick_cookies.txt"],
    PlatformType.PINTEREST: ["cookies_pinterest.txt", "pinterest_cookies.txt"],
}

# Principales archivos de cookies a auditar en la visualización
AUDIT_COOKIE_TARGETS: List[Tuple[str, str, Optional[PlatformType]]] = [
    ("cookies.txt", "🌐 Universal (yt-dlp estándar)", None),
    ("cookies_youtube.txt", "🔴 YouTube", PlatformType.YOUTUBE),
    ("cookies_instagram.txt", "📸 Instagram", PlatformType.INSTAGRAM),
    ("cookies_tiktok.txt", "🎵 TikTok", PlatformType.TIKTOK),
    ("cookies_twitter.txt", "🐦 Twitter / X", PlatformType.TWITTER),
    ("cookies_twitch.txt", "🟣 Twitch", PlatformType.TWITCH),
    ("cookies_facebook.txt", "🔵 Facebook", PlatformType.FACEBOOK),
    ("cookies_reddit.txt", "🟠 Reddit", PlatformType.REDDIT),
]


def parse_browser_spec(cookies_from: str) -> Tuple[str, Optional[str]]:
    """
    Parsea una especificación de navegador y perfil opcional:
    - 'brave' -> ('brave', None)
    - 'brave:Default' -> ('brave', 'Default')
    - 'chrome:Profile 1' -> ('chrome', 'Profile 1')
    - 'edge:Profile 2' -> ('edge', 'Profile 2')
    - 'firefox:default-release' -> ('firefox', 'default-release')
    """
    if not cookies_from or not isinstance(cookies_from, str):
        return ("", None)

    spec = cookies_from.strip()
    if ':' in spec:
        parts = spec.split(':', 1)
        browser = parts[0].strip().lower()
        profile = parts[1].strip() if parts[1].strip() else None
        return (browser, profile)
    return (spec.lower(), None)


def _get_chromium_user_data_path(browser_name: str) -> Optional[Path]:
    """Retorna la ruta al directorio User Data de un navegador Chromium en Windows si existe"""
    b = browser_name.lower()
    local_appdata = os.environ.get('LOCALAPPDATA', '')
    appdata = os.environ.get('APPDATA', '')

    paths_map = {
        'chrome': Path(local_appdata) / 'Google' / 'Chrome' / 'User Data' if local_appdata else None,
        'brave': Path(local_appdata) / 'BraveSoftware' / 'Brave-Browser' / 'User Data' if local_appdata else None,
        'edge': Path(local_appdata) / 'Microsoft' / 'Edge' / 'User Data' if local_appdata else None,
        'vivaldi': Path(local_appdata) / 'Vivaldi' / 'User Data' if local_appdata else None,
        'opera': Path(appdata) / 'Opera Software' / 'Opera Stable' if appdata else None,
        'opera_gx': Path(appdata) / 'Opera Software' / 'Opera GX Stable' if appdata else None,
    }
    target = paths_map.get(b)
    if target and target.exists():
        return target
    return None


def get_available_browser_profiles(browser_name: str) -> List[str]:
    """
    Descubre perfiles de usuario disponibles para un navegador Chromium en Windows.
    Retorna nombres como ['Default', 'Profile 1', 'Profile 2'] si existen.
    """
    b = browser_name.lower()
    user_data = _get_chromium_user_data_path(b)
    if not user_data or not user_data.exists():
        return ['Default'] if b in ('chrome', 'brave', 'edge', 'vivaldi', 'opera') else []

    profiles: List[str] = []

    # Comprobar directorio 'Default'
    if (user_data / 'Default').is_dir():
        profiles.append('Default')

    # Comprobar directorios tipo 'Profile 1', 'Profile 2', etc.
    try:
        for item in user_data.iterdir():
            if item.is_dir() and item.name.startswith('Profile '):
                profiles.append(item.name)
    except Exception:
        pass

    # Si es Opera o estructura sin carpetas de perfil directas pero con cookies
    if not profiles and ((user_data / 'Network' / 'Cookies').exists() or (user_data / 'Cookies').exists()):
        profiles.append('Default')

    return sorted(profiles, key=lambda x: (x != 'Default', x)) if profiles else ['Default']


def extract_cookies_lock_safe(browser_name: str, profile: Optional[str] = None) -> Optional[Path]:
    """
    Copia la base de datos de cookies de SQLite y archivos de clave a una carpeta temporal
    para evitar conflictos de bloqueo exclusivo (WinError 32) cuando el navegador Chromium está en ejecución en Windows.
    Retorna la ruta al archivo de cookies copiado o None si no se localizó.
    """
    b = browser_name.lower()
    user_data = _get_chromium_user_data_path(b)
    if not user_data or not user_data.exists():
        return None

    target_profile = profile or 'Default'
    profile_dir = user_data / target_profile if (user_data / target_profile).is_dir() else user_data

    # Localizar archivo de cookies
    cookie_file = None
    for candidate in [profile_dir / 'Network' / 'Cookies', profile_dir / 'Cookies']:
        if candidate.exists():
            cookie_file = candidate
            break

    if not cookie_file:
        return None

    try:
        temp_dir = Path(tempfile.mkdtemp(prefix=f"locksafe_{b}_{target_profile}_"))
        temp_cookies = temp_dir / "Cookies"

        # Copia segura de archivo SQLite de cookies
        with open(cookie_file, 'rb') as src, open(temp_cookies, 'wb') as dst:
            dst.write(src.read())

        # Copiar también Local State si existe para descifrado de claves DPAPI/AES
        local_state = user_data / 'Local State'
        if local_state.exists():
            temp_local_state = temp_dir / 'Local State'
            with open(local_state, 'rb') as src, open(temp_local_state, 'wb') as dst:
                dst.write(src.read())

        return temp_cookies
    except Exception:
        return None


def find_cookie_file(filename: str) -> Optional[Path]:
    """
    Busca un archivo de cookies con resolución inteligente:
    1. Si es una ruta directa existente (absoluta o relativa)
    2. Dentro de la carpeta 'cookies/' (ej. cookies/cookies_youtube.txt)
    3. En el directorio raíz del proyecto (fallback de compatibilidad)
    """
    if not filename:
        return None
    p_direct = Path(filename)
    if p_direct.exists():
        return p_direct
    p_in_cookies = COOKIES_DIR / p_direct.name
    if p_in_cookies.exists():
        return p_in_cookies
    p_in_root = Path(p_direct.name)
    if p_in_root.exists():
        return p_in_root
    return None


def get_platform_cookie_files(platform: Optional[PlatformType] = None) -> List[str]:
    """Retorna la lista de nombres de archivos de cookies candidatos para una plataforma dada"""
    if platform and platform in PLATFORM_COOKIE_FILES:
        return list(PLATFORM_COOKIE_FILES[platform])
    return ["cookies.txt", "youtube_cookies.txt"]


def get_cookie_opts(
    url: Optional[str] = None,
    cookies_from: Optional[str] = None,
    cookies_file: Optional[str] = None,
    default_cookies_from: Optional[str] = None,
    default_cookies_file: Optional[str] = None,
    platform: Optional[PlatformType] = None
) -> Dict[str, Any]:
    """
    Configura opciones de cookies con búsqueda en cascada inteligente multi-sitio:
    1. Archivo de cookies explícito pasado por parámetro (cookies_file o default_cookies_file)
    2. Navegador explícito pasado por parámetro (cookies_from o default_cookies_from), con soporte de perfiles (ej. 'brave:Default')
    3. Archivo específico de la plataforma en cookies/ o raíz (ej. cookies/cookies_instagram.txt)
    4. Archivo genérico cookies/cookies.txt o cookies.txt
    5. Archivo legado cookies/youtube_cookies.txt o youtube_cookies.txt (para YouTube o fallback)
    """
    opts: Dict[str, Any] = {}

    # Manejo de llamada posicional con nombre de navegador o navegador:perfil: get_cookie_opts('firefox') o get_cookie_opts('brave:Default')
    if url and isinstance(url, str) and cookies_from is None:
        cand_b, _ = parse_browser_spec(url)
        if cand_b in SUPPORTED_BROWSERS:
            cookies_from = url
            url = None

    # 1. Archivo de cookies explícito o por defecto
    target_file = cookies_file or default_cookies_file
    if target_file:
        found_file = find_cookie_file(target_file)
        if found_file:
            opts['cookiefile'] = str(found_file.resolve())
            return opts

    # 2. Navegador explícito o por defecto (con soporte para browser:profile)
    target_browser = cookies_from or default_cookies_from
    if target_browser:
        browser, profile = parse_browser_spec(target_browser)
        opts['cookiesfrombrowser'] = (browser, profile, None, None)
        return opts

    # Determinar la plataforma si se especificó url o platform
    target_platform = platform
    if target_platform is None and url:
        target_platform = get_platform_info(url).type

    # 3. Archivo específico de la plataforma si existe en disco (en cookies/ o en raíz)
    if target_platform and target_platform in PLATFORM_COOKIE_FILES:
        for filename in PLATFORM_COOKIE_FILES[target_platform]:
            found_file = find_cookie_file(filename)
            if found_file:
                opts['cookiefile'] = str(found_file.resolve())
                return opts

    # 4. Archivo genérico cookies.txt en cookies/ o directorio raíz
    generic_cookies = find_cookie_file('cookies.txt')
    if generic_cookies:
        opts['cookiefile'] = str(generic_cookies.resolve())
        return opts

    # 5. Archivo legado youtube_cookies.txt (para YouTube o como fallback)
    legacy_cookies = find_cookie_file('youtube_cookies.txt')
    if legacy_cookies:
        opts['cookiefile'] = str(legacy_cookies.resolve())
        return opts

    return opts


def _count_valid_cookies_in_file(file_path: Path) -> Tuple[int, int]:
    """Retorna (número_de_cookies, tamaño_en_bytes) de un archivo de cookies Netscape"""
    if not file_path.exists():
        return (0, 0)
    size_bytes = file_path.stat().st_size
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            valid_lines = [line for line in f if line.strip() and not line.startswith('#')]
        return (len(valid_lines), size_bytes)
    except Exception:
        return (0, size_bytes)


def check_cookies_status(console_instance: Optional[Console] = None) -> None:
    """
    Comprueba y diagnostica el estado de cookies multi-plataforma:
    - Archivos de cookies detectados en la carpeta cookies/ y en el proyecto
    - Sesiones activas en navegadores web soportados (YouTube, TikTok, Instagram, Twitter/X, Twitch, Facebook, Reddit)
    - Recomendaciones y prevención de bloqueos antibot/login por plataforma
    """
    c = console_instance or console
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    c.print(Panel(
        "[bold cyan]🍪 Diagnóstico Multi-Plataforma de Cookies y Sesiones[/bold cyan]\n"
        "[dim]Auditoría de archivos de cookies locales (carpeta cookies/) y sesiones de navegadores para YouTube, TikTok, Instagram, Twitter/X, Twitch y más.[/dim]",
        border_style="cyan",
        expand=False
    ))

    # =========================================================================
    # 1. Tabla de Archivos de Cookies Locales
    # =========================================================================
    files_table = Table(
        title="[bold green]📁 Archivos de Cookies en el Proyecto (carpeta cookies/)[/bold green]",
        header_style="bold magenta",
        border_style="green"
    )
    files_table.add_column("Archivo / Ruta", style="bold white", justify="left")
    files_table.add_column("Plataforma / Alcance", style="cyan", justify="left")
    files_table.add_column("Estado", justify="center")
    files_table.add_column("Detalles / Cookies", justify="left")

    shown_filenames: Set[str] = set()

    for filename, description, p_type in AUDIT_COOKIE_TARGETS:
        shown_filenames.add(filename.lower())
        found_path = find_cookie_file(filename)
        if found_path:
            count, size = _count_valid_cookies_in_file(found_path)
            files_table.add_row(
                f"📁 {found_path.as_posix()}",
                description,
                "[bold green]✅ Detectado y Activo[/bold green]",
                f"{count} cookies registradas ({format_bytes(size)})"
            )
        else:
            files_table.add_row(
                f"📁 cookies/{filename}",
                description,
                "[dim]No presente[/dim]",
                "Opcional (guarda en cookies/ para autenticar)"
            )

    # Buscar si existen archivos adicionales con patrón cookies_*.txt o *_cookies.txt en cookies/ o raíz
    try:
        candidate_paths: List[Path] = []
        if COOKIES_DIR.exists():
            candidate_paths.extend(list(COOKIES_DIR.glob('*.txt')))
        candidate_paths.extend(list(Path('.').glob('*cookies*.txt')))

        for extra_file in candidate_paths:
            if extra_file.name.lower() not in shown_filenames and extra_file.is_file():
                shown_filenames.add(extra_file.name.lower())
                count, size = _count_valid_cookies_in_file(extra_file)
                files_table.add_row(
                    f"📁 {extra_file.as_posix()}",
                    "Personalizado / Detectado",
                    "[bold green]✅ Detectado[/bold green]",
                    f"{count} cookies registradas ({format_bytes(size)})"
                )
    except Exception:
        pass

    c.print(files_table)
    c.print()

    # =========================================================================
    # 2. Tabla de Sesiones en Navegadores Web
    # =========================================================================
    browsers_table = Table(
        title="[bold green]🌐 Estado de Sesiones en Navegadores Web[/bold green]",
        header_style="bold magenta",
        border_style="green"
    )
    browsers_table.add_column("Navegador / Perfiles", style="bold white", justify="left")
    browsers_table.add_column("Estado", justify="center")
    browsers_table.add_column("Sesiones Detectadas / Diagnóstico", justify="left")

    has_appbound_or_locked = False

    with c.status("[bold cyan]🔍 Analizando navegadores instalados y sesiones activas...", spinner="dots"):
        for b in SUPPORTED_BROWSERS:
            profiles = get_available_browser_profiles(b)
            profile_label = f" ({', '.join(profiles)})" if len(profiles) > 1 else ""
            browser_display = f"🌐 {b.capitalize()}{profile_label}"

            buf = io.StringIO()
            try:
                with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
                    ydl = yt_dlp.YoutubeDL({
                        'cookiesfrombrowser': (b, None, None, None),
                        'quiet': True,
                        'no_warnings': True
                    })
                    jar = ydl.cookiejar
                    
                    # Auditar cookies presentes por cada plataforma soportada
                    detected_platforms: List[str] = []
                    for p_type, (p_name, domains) in PLATFORM_COOKIE_DOMAINS.items():
                        cnt = len([ck for ck in jar if any(d in (ck.domain or '').lower() for d in domains)])
                        if cnt > 0:
                            detected_platforms.append(f"{p_name} ({cnt})")
                    
                    if detected_platforms:
                        browsers_table.add_row(
                            browser_display,
                            "[bold green]✅ Sesión Activa[/bold green]",
                            f"Sesiones en: {', '.join(detected_platforms)}"
                        )
                    else:
                        total_cookies = len(list(jar))
                        if total_cookies > 0:
                            browsers_table.add_row(
                                browser_display,
                                "[bold yellow]⚠️ Sin Redes Sociales[/bold yellow]",
                                f"Navegador accesible ({total_cookies} cookies en otros dominios)"
                            )
                        else:
                            browsers_table.add_row(
                                browser_display,
                                "[bold yellow]⚠️ Sin Sesión[/bold yellow]",
                                "Navegador accesible pero sin cookies registradas"
                            )
            except Exception as e:
                err_text = (str(e) + " " + buf.getvalue()).lower()
                if any(kw in err_text for kw in ("app-bound", "appbound", "dpapi", "cryptunprotectdata", "decrypt")):
                    has_appbound_or_locked = True
                    browsers_table.add_row(
                        browser_display,
                        "[bold yellow]🔒 Cifrado App-Bound / DPAPI[/bold yellow]",
                        "Protegido por App-Bound encryption de Windows. Usa archivo cookies.txt en cookies/"
                    )
                elif any(kw in err_text for kw in ("database", "copy", "locked", "permission", "access", "winerror 32", "in use")):
                    has_appbound_or_locked = True
                    browsers_table.add_row(
                        browser_display,
                        "[bold yellow]🔒 Base de Datos Bloqueada[/bold yellow]",
                        "Bloqueado por navegador en ejecución. Cierra el navegador o usa cookies/"
                    )
                elif any(kw in err_text for kw in ("could not find", "not found", "no such")):
                    browsers_table.add_row(
                        browser_display,
                        "[dim]No instalado[/dim]",
                        "No se encontró base de datos del navegador"
                    )
                else:
                    browsers_table.add_row(
                        browser_display,
                        "[red]✗ Error[/red]",
                        f"{str(e)[:45]}..."
                    )

    c.print(browsers_table)
    c.print()

    # =========================================================================
    # 3. Diagnóstico de Cifrado App-Bound (Windows Chromium) si aplica
    # =========================================================================
    if has_appbound_or_locked:
        appbound_panel = (
            "[bold yellow]⚠️ Diagnóstico de Cifrado App-Bound y Bloqueos de Archivo (Windows Chromium):[/bold yellow]\n\n"
            "• [bold white]Cifrado App-Bound (Chrome 127+, Brave, Edge):[/bold white] Las versiones recientes en Windows cifran las cookies con una clave vinculada exclusivamente al ejecutable del navegador.\n"
            "• [bold white]Bloqueo WinError 32:[/bold white] Si el navegador está abierto, SQLite mantiene un bloqueo exclusivo sobre el archivo de cookies.\n"
            "• [bold green]Solución 100% fiable:[/bold green] Exporta tus cookies en formato Netscape usando la extensión [bold yellow]'Get cookies.txt LOCALLY'[/bold yellow] y colócalas en la carpeta [bold yellow]'cookies/'[/bold yellow] (ej. [bold yellow]cookies/cookies_youtube.txt[/bold yellow])."
        )
        c.print(Panel(appbound_panel, title="[bold yellow]🔒 Aviso de Seguridad y Cifrado App-Bound[/bold yellow]", border_style="yellow", expand=False))
        c.print()

    # =========================================================================
    # 4. Panel de Consejos y Prevención por Plataforma
    # =========================================================================
    consejos = (
        "[bold cyan]💡 Consejos por Plataforma para Evitar Bloqueos y Restricciones:[/bold cyan]\n\n"
        "• 🔴 [bold red]YouTube:[/bold red] Requiere cookies para videos con restricción de edad (18+), contenido de miembros o cuando se activa el desafío antibot (HTTP 403).\n"
        "• 📸 [bold magenta]Instagram:[/bold magenta] Imprescindible para descargar Reels privados, Stories, perfiles completos y evitar el bloqueo por 'Login wall' de Meta.\n"
        "• 🐦 [bold blue]Twitter / X:[/bold blue] Necesario para acceder a tweets con contenido sensible (NSFW), cuentas protegidas o evitar límites de tasa (rate limits).\n"
        "• 🎵 [bold cyan]TikTok:[/bold cyan] Recomendado para colecciones privadas, videos guardados o evitar desafíos captcha durante descargas continuas.\n"
        "• 🟣 [bold purple]Twitch:[/bold purple] Requerido para VODs y directos exclusivos para suscriptores (sub-only).\n"
        "• 🔵 [bold blue]Facebook:[/bold blue] Requerido para videos en grupos cerrados o publicaciones privadas autorizadas."
    )
    c.print(Panel(consejos, title="[bold cyan]🛡️ Prevención de Bloqueos y Consejos por Plataforma[/bold cyan]", border_style="cyan", expand=False))
    c.print()

    # =========================================================================
    # 5. Guía de Exportación y Comandos CLI
    # =========================================================================
    instrucciones = (
        "[bold cyan]📌 Cómo Exportar y Usar Cookies Multi-Plataforma:[/bold cyan]\n\n"
        "1. [bold white]Método Recomendado (Carpeta cookies/):[/bold white]\n"
        "   • Las cookies se almacenan organizadas en la carpeta [bold yellow]'cookies/'[/bold yellow] del proyecto.\n"
        "   • Instala en tu navegador la extensión [bold yellow]'Get cookies.txt LOCALLY'[/bold yellow] o [bold yellow]'Cookie-Editor'[/bold yellow].\n"
        "   • Abre la red social deseada (Instagram, Twitter, YouTube, TikTok, etc.) con tu sesión iniciada.\n"
        "   • Exporta las cookies en formato Netscape (.txt) y guárdalas dentro de [bold yellow]'cookies/'[/bold yellow] como:\n"
        "     - [bold white]cookies/cookies.txt[/bold white] (se aplicará como cookie universal a cualquier plataforma)\n"
        "     - [bold white]cookies/cookies_instagram.txt[/bold white] (específico para Instagram)\n"
        "     - [bold white]cookies/cookies_tiktok.txt[/bold white] (específico para TikTok)\n"
        "     - [bold white]cookies/cookies_twitter.txt[/bold white] (específico para Twitter / X)\n"
        "     - [bold white]cookies/cookies_youtube.txt[/bold white] o [bold white]cookies/youtube_cookies.txt[/bold white] (específico para YouTube)\n"
        "     - [bold white]cookies/cookies_twitch.txt[/bold white] (específico para Twitch)\n"
        "     - [bold white]cookies/cookies_facebook.txt[/bold white] (específico para Facebook)\n"
        "   • El programa las detectará y aplicará automáticamente según la URL a descargar.\n\n"
        "2. [bold white]Método Directo por Navegador (CLI):[/bold white]\n"
        "   • [green]python youtube_downloader.py download \"URL\" --cookies-from firefox[/green]\n"
        "   • [green]python youtube_downloader.py download \"URL\" --cookies-from brave:Default[/green]\n"
        "   • [green]python youtube_downloader.py download \"URL\" --cookies-from \"chrome:Profile 1\"[/green]\n\n"
        "3. [bold white]Método Archivo Explícito (CLI):[/bold white]\n"
        "   • [green]python youtube_downloader.py download \"URL\" --cookies-file cookies/mis_cookies.txt[/green]"
    )
    c.print(Panel(instrucciones, title="[bold cyan]📖 Guía de Uso de Cookies[/bold cyan]", border_style="cyan", expand=False))
