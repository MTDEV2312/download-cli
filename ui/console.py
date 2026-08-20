"""
Módulo de interfaz de consola enriquecida con Rich (paneles, tablas, banners y mensajes de error).
"""

from typing import Optional
from rich.console import Console
from rich.panel import Panel

from utils.platform_detector import detect_platform, PlatformType

# Instancia global de Console (legacy_windows=False asegura soporte completo de caracteres y bordes)
console = Console(legacy_windows=False)


def print_banner(console_instance: Optional[Console] = None):
    """Imprime el banner principal de la aplicación"""
    c = console_instance or console
    banner_text = (
        "[bold cyan]🎬 Universal Video & Audio Downloader CLI[/bold cyan]\n"
        "[dim]Descarga de 1800+ sitios: YouTube, TikTok, Instagram, Twitter/X, Twitch, SoundCloud, Bandcamp, Vimeo, Kick, streams HLS/DASH y web genérica[/dim]"
    )
    c.print(Panel(banner_text, border_style="cyan", expand=False))


def print_success(message: str, details: str = "", console_instance: Optional[Console] = None):
    """Muestra un panel estilizado de éxito en verde"""
    c = console_instance or console
    content = f"[bold green]✓ {message}[/bold green]"
    if details:
        content += f"\n[dim white]{details}[/dim white]"
    c.print(Panel(content, title="[bold green]✅ Éxito[/bold green]", border_style="green", expand=False))


def print_error(message: str, details: str = "", console_instance: Optional[Console] = None):
    """Muestra un panel estilizado de error en rojo"""
    c = console_instance or console
    content = f"[bold red]✗ {message}[/bold red]"
    if details:
        content += f"\n[yellow]{details}[/yellow]"
    c.print(Panel(content, title="[bold red]❌ Error[/bold red]", border_style="red", expand=False))


def print_warning(message: str, details: str = "", console_instance: Optional[Console] = None):
    """Muestra un panel estilizado de advertencia en amarillo"""
    c = console_instance or console
    content = f"[bold yellow]⚠️  {message}[/bold yellow]"
    if details:
        content += f"\n[dim]{details}[/dim]"
    c.print(Panel(content, title="[bold yellow]Advertencia[/bold yellow]", border_style="yellow", expand=False))


def print_info_panel(message: str, title: str = "Información", console_instance: Optional[Console] = None):
    """Muestra un panel de información en azul/cian"""
    c = console_instance or console
    c.print(Panel(message, title=f"[bold cyan]ℹ️  {title}[/bold cyan]", border_style="cyan", expand=False))


def handle_download_error(e: Exception, context_url: str = "", console_instance: Optional[Console] = None):
    """
    Diagnóstico inteligente, adaptativo y contextual de errores según la plataforma detectada.
    Proporciona sugerencias claras para resolver bloqueos 403, cookies, autenticación, login-walls,
    captchas, streams HLS/DASH caídos y dependencias como FFmpeg o JS runtimes.
    """
    c = console_instance or console
    err_msg = str(e)
    err_lower = err_msg.lower()

    # Detección contextual de plataforma
    platform_type = PlatformType.GENERIC
    platform_name = "Web Genérica"
    if context_url:
        platform_type, platform_name, _ = detect_platform(context_url)

    # Banderas generales de error
    is_403_or_bot = "403" in err_msg or "forbidden" in err_lower or any(
        k in err_lower for k in ("bot", "sign in", "confirm you", "n challenge", "account is terminated", "potoken", "po_token", "rate-limit", "rate limit", "too many requests", "429")
    )
    is_dpapi = "dpapi" in err_lower or "could not copy chrome cookie" in err_lower or ("could not find" in err_lower and "cookie" in err_lower) or "failed to decrypt" in err_lower or ("crypto" in err_lower and "cookie" in err_lower)
    is_ffmpeg = "ffmpeg" in err_lower or "ffprobe" in err_lower
    is_drm = any(k in err_lower for k in ("drm", "encrypted", "widevine", "playready", "fairplay", "digital rights management"))
    is_private = any(k in err_lower for k in ("private video", "video unavailable", "members-only", "this video is only available", "is private", "login required", "account is private", "not authorized"))
    is_geo = any(k in err_lower for k in ("geo", "country", "not available in your region", "blocked in your country", "geolocation"))

    # Diagnósticos especializados por plataforma y condición

    # 1. Error de descifrado DPAPI en navegadores Chromium
    if is_dpapi:
        print_error(
            "Error al extraer cookies del navegador (Protección DPAPI)",
            "Los navegadores basados en Chromium (Chrome, Edge, Brave, Opera) bloquean el descifrado directo de cookies cuando están en ejecución o debido a restricciones del sistema.\n\n"
            "💡 [bold cyan]Soluciones recomendadas:[/bold cyan]\n"
            "  1. Cierra el navegador antes de iniciar la descarga, o usa Firefox: [bold white]--cookies-from firefox[/bold white]\n"
            "  2. Exporta tus cookies con la extensión [bold white]'Get cookies.txt LOCALLY'[/bold white] y guárdalas como [bold white]cookies.txt[/bold white] o [bold white]cookies_[plataforma].txt[/bold white].\n"
            "  3. Ejecuta [bold white]python youtube_downloader.py cookies[/bold white] para diagnosticar sesiones disponibles.",
            console_instance=c
        )

    # 2. Error de dependencias (FFmpeg / ffprobe)
    elif is_ffmpeg:
        print_error(
            "Error relacionado con FFmpeg / Códecs multimedia",
            "FFmpeg es indispensable para combinar pistas de video/audio, incrustar carátulas/subtítulos o convertir formatos.\n\n"
            "💡 [bold cyan]Soluciones recomendadas:[/bold cyan]\n"
            "  1. Ejecuta el script instalador: [bold white]instalar_ffmpeg.bat[/bold white]\n"
            "  2. O instala mediante Windows Package Manager: [bold white]winget install ffmpeg[/bold white]\n"
            "  3. Asegúrate de reiniciar la terminal tras instalar FFmpeg para actualizar el PATH del sistema.",
            console_instance=c
        )

    # 3. Flujo protegido con DRM comercial
    elif is_drm:
        print_error(
            "Contenido protegido por DRM comercial (Widevine / FairPlay)",
            "El flujo multimedia solicitado está protegido mediante encriptación DRM (Digital Rights Management).\n\n"
            "💡 [bold cyan]Información:[/bold cyan]\n"
            "  • Por razones técnicas y legales, yt-dlp no puede desencriptar streams con DRM comercial.\n"
            "  • Solo contenidos con streams abiertos o manifiestos sin DRM pueden ser descargados.",
            console_instance=c
        )

    # 4. Instagram: Login-wall, cuentas privadas o rate-limit
    elif platform_type == PlatformType.INSTAGRAM or "instagram" in err_lower:
        print_error(
            "Restricción de acceso en Instagram (Login-wall / Cuenta Privada)",
            "Instagram requiere inicio de sesión para visualizar este Reel, Story, post o perfil privado, o ha aplicado un límite temporal a tu IP.\n\n"
            "💡 [bold cyan]Soluciones recomendadas:[/bold cyan]\n"
            "  1. Usa cookies de tu navegador: [bold white]--cookies-from chrome[/bold white] (o firefox, edge, brave)\n"
            "  2. Exporta tus cookies de Instagram a [bold white]cookies_instagram.txt[/bold white] o [bold white]cookies.txt[/bold white] en la carpeta del programa.\n"
            "  3. Si la cuenta es privada, comprueba que tu perfil tenga autorización para verla.\n"
            "  4. Actualiza yt-dlp: [bold white]pip install --upgrade yt-dlp[/bold white]",
            console_instance=c
        )

    # 5. Twitter / X: Contenido sensible, tweets eliminados o restricciones de sesión
    elif platform_type == PlatformType.TWITTER or "twitter" in err_lower or "x.com" in err_lower:
        print_error(
            "Contenido restringido o no disponible en Twitter / X",
            "El tweet contiene material sensible (NSFW), requiere sesión activa para visualizarse, pertenece a una cuenta protegida o ha sido eliminado.\n\n"
            "💡 [bold cyan]Soluciones recomendadas:[/bold cyan]\n"
            "  1. Autentica con tu navegador: [bold white]--cookies-from chrome[/bold white] (o firefox, edge)\n"
            "  2. O guarda tus cookies en [bold white]cookies_twitter.txt[/bold white] o [bold white]cookies.txt[/bold white].\n"
            "  3. Verifica en el navegador que el tweet aún exista y esté visible públicamente.",
            console_instance=c
        )

    # 6. TikTok: Captchas antibot, videos privados o bloqueo regional
    elif platform_type == PlatformType.TIKTOK or "tiktok" in err_lower:
        print_error(
            "Restricción / Desafío antibot en TikTok",
            "TikTok ha solicitado resolver un desafío antibot (Captcha), el video es privado o existe un bloqueo regional.\n\n"
            "💡 [bold cyan]Soluciones recomendadas:[/bold cyan]\n"
            "  1. Pasa cookies de tu navegador con sesión abierta: [bold white]--cookies-from edge[/bold white] (o chrome, firefox)\n"
            "  2. O exporta tus cookies a [bold white]cookies_tiktok.txt[/bold white].\n"
            "  3. Actualiza yt-dlp para obtener los últimos extractores de TikTok: [bold white]pip install --upgrade yt-dlp[/bold white]",
            console_instance=c
        )

    # 7. Twitch: VODs sub-only o stream en vivo finalizado
    elif platform_type == PlatformType.TWITCH or "twitch" in err_lower:
        print_error(
            "VOD o transmisión no disponible en Twitch",
            "El VOD es exclusivo para suscriptores de pago (sub-only), el stream en vivo ha finalizado o el video fue archivado.\n\n"
            "💡 [bold cyan]Soluciones recomendadas:[/bold cyan]\n"
            "  1. Si eres suscriptor del canal, usa [bold white]--cookies-from [navegador][/bold white] o [bold white]cookies_twitch.txt[/bold white].\n"
            "  2. Si es una transmisión en directo, confirma que el canal esté transmitiendo en este momento.",
            console_instance=c
        )

    # 8. YouTube: 403 Forbidden, desafíos antibot / poToken
    elif platform_type == PlatformType.YOUTUBE or "youtube" in err_lower or "youtu.be" in err_lower:
        print_error(
            "Acceso bloqueado por YouTube (403 Forbidden / Anti-Bot)",
            "YouTube requiere verificación de sesión, resolución JS poToken o detectó tráfico automatizado.\n\n"
            "💡 [bold cyan]Soluciones recomendadas:[/bold cyan]\n"
            "  1. Usa cookies de tu navegador: [bold white]--cookies-from firefox[/bold white] (o brave, edge, chrome)\n"
            "  2. O exporta tu sesión a [bold white]youtube_cookies.txt[/bold white] o [bold white]cookies.txt[/bold white].\n"
            "  3. Asegúrate de tener Deno o Node.js instalado ([bold white]winget install DenoLand.Deno[/bold white]).\n"
            "  4. Actualiza yt-dlp: [bold white]pip install --upgrade yt-dlp[/bold white]",
            console_instance=c
        )

    # 9. Streams directos / Manifiestos HLS/DASH (403, 404, token expirado)
    elif platform_type == PlatformType.DIRECT_STREAM or any(ext in err_lower for ext in (".m3u8", ".mpd", "manifest", "fragment", "hls", "dash")):
        print_error(
            "Error al descargar Stream Directo / Manifiesto HLS/DASH",
            "El enlace .m3u8 o .mpd no responde, el token de sesión ha expirado o el servidor requiere cabeceras HTTP específicas.\n\n"
            "💡 [bold cyan]Soluciones recomendadas:[/bold cyan]\n"
            "  1. Copia un enlace fresco del stream desde las herramientas de desarrollador del navegador (pestaña Red / Network).\n"
            "  2. Comprueba que el stream no requiera autenticación o cookies de sesión.\n"
            "  3. Verifica que la transmisión en vivo siga activa.",
            console_instance=c
        )

    # 10. Bloqueo geográfico genérico
    elif is_geo:
        print_error(
            "Contenido con restricción geográfica",
            "Este contenido no está disponible en tu región o país debido a bloqueos territoriales del proveedor.\n\n"
            "💡 [bold cyan]Solución:[/bold cyan]\n"
            "  Utiliza una conexión VPN con salida en el país de origen del contenido.",
            console_instance=c
        )

    # 11. Contenido privado o no disponible genérico
    elif is_private:
        print_error(
            "Contenido privado o no disponible",
            "El video/audio es privado, fue eliminado o requiere membresía especial.\n\n"
            "💡 [bold cyan]Solución:[/bold cyan]\n"
            "  Si tienes acceso autorizado con tu cuenta, proporciona cookies de sesión (--cookies-from o archivo cookies.txt).",
            console_instance=c
        )

    # 12. Bloqueo 403 o bot genérico
    elif is_403_or_bot:
        print_error(
            f"Acceso restringido por el servidor ({platform_name})",
            f"El servidor de {platform_name} denegó la solicitud (403 Forbidden / Límite de tasa / Verificación de sesión).\n\n"
            "💡 [bold cyan]Soluciones recomendadas:[/bold cyan]\n"
            "  1. Usa cookies de tu navegador: [bold white]--cookies-from [navegador][/bold white]\n"
            "  2. O exporta tus cookies a [bold white]cookies.txt[/bold white] en la carpeta del programa.\n"
            "  3. Actualiza yt-dlp: [bold white]pip install --upgrade yt-dlp[/bold white]",
            console_instance=c
        )

    # 13. Fallback general
    else:
        print_error(f"Error durante la descarga ({platform_name})", err_msg, console_instance=c)
        c.print("[dim cyan]💡 Tip: Puedes consultar información previa con: python youtube_downloader.py info <URL>[/dim cyan]")
