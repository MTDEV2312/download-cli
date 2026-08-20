"""
Test Suite para la arquitectura modular de Universal & YouTube Downloader (Fases 1, 2, 3 y 4).
Verifica:
1. Módulos utils: formatters, clipboard, platform_detector
2. Módulos ui: console (print_banner, handle_download_error contextual por plataforma),
   notifier (show_desktop_notification, get_notification_title contextual),
   progress (RichDownloadProgress, RichPlaylistProgress, RichConcurrentBatchProgress, classify_stream_label, clean_stream_title)
3. Módulos core: cookies (multi-sitio, browser audit), extractor (UniversalExtractor + Selector Adaptativo),
   downloader (UniversalDownloader con compatibilidad YouTubeDownloader)
"""

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from io import StringIO
from rich.console import Console

# Utils
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
    detect_platform,
    get_platform_info,
    is_valid_url,
    is_valid_media_url,
)

# UI
from ui.console import (
    console,
    print_banner,
    print_success,
    print_error,
    print_warning,
    print_info_panel,
    handle_download_error,
)
from ui.notifier import (
    show_desktop_notification,
    get_notification_title,
    HAS_WINOTIFY,
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

# Core
from core.cookies import get_cookie_opts, check_cookies_status, find_cookie_file, COOKIES_DIR, SUPPORTED_BROWSERS
from core.extractor import (
    get_raw_info,
    get_video_info,
    get_media_info,
    display_info,
    interactive_select_format,
    _parse_format_dimensions,
)
from core.downloader import (
    UniversalDownloader,
    YouTubeDownloader,
    MediaDownloader,
)


class TestFormatters(unittest.TestCase):
    def test_format_duration(self):
        self.assertEqual(format_duration(0), "Desconocida")
        self.assertEqual(format_duration(None), "Desconocida")
        self.assertEqual(format_duration(45), "0m 45s")
        self.assertEqual(format_duration(125), "2m 05s")
        self.assertEqual(format_duration(3665), "1h 01m 05s")

    def test_format_bytes(self):
        self.assertEqual(format_bytes(0), "N/A")
        self.assertEqual(format_bytes(None), "N/A")
        self.assertEqual(format_bytes(1024), "1.0 KB")
        self.assertEqual(format_bytes(1024 * 1024 * 5), "5.0 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024 * 2), "2.00 GB")

    def test_format_views(self):
        self.assertEqual(format_views(None), "N/A")
        self.assertEqual(format_views(500), "500 vistas")
        self.assertEqual(format_views(1500), "1.5K vistas")
        self.assertEqual(format_views(2500000), "2.5M vistas")

    def test_format_date(self):
        self.assertEqual(format_date("20260819"), "2026-08-19")
        self.assertEqual(format_date(""), "N/A")
        self.assertEqual(format_date(None), "N/A")

    def test_clean_codec_name(self):
        self.assertEqual(clean_codec_name("avc1.640028"), "H.264 (AVC)")
        self.assertEqual(clean_codec_name("vp09.00.51"), "VP9")
        self.assertEqual(clean_codec_name("av01.0.08M"), "AV1")
        self.assertEqual(clean_codec_name("mp4a.40.2"), "AAC")
        self.assertEqual(clean_codec_name("opus"), "Opus")
        self.assertEqual(clean_codec_name("none"), "-")

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename('Video: "Test" <1>? *'), "Video Test 1")
        self.assertEqual(sanitize_filename(''), "Video")


class TestClipboard(unittest.TestCase):
    def test_is_youtube_url(self):
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_youtube_url("https://youtu.be/dQw4w9WgXcQ"))
        self.assertTrue(is_youtube_url("https://www.youtube.com/playlist?list=PL1234567890"))
        self.assertTrue(is_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ"))
        self.assertFalse(is_youtube_url("https://vimeo.com/123456"))
        self.assertFalse(is_youtube_url("not a url"))
        self.assertFalse(is_youtube_url(None))

    def test_is_valid_url(self):
        self.assertTrue(is_valid_url("https://www.tiktok.com/@user/video/123"))
        self.assertTrue(is_valid_url("https://www.instagram.com/reel/123"))
        self.assertTrue(is_valid_url("https://x.com/user/status/123"))
        self.assertTrue(is_valid_url("https://stream.server.com/live.m3u8"))
        self.assertFalse(is_valid_url(""))
        self.assertFalse(is_valid_url("invalid_url"))

    def test_detect_platform(self):
        self.assertEqual(detect_platform("https://www.youtube.com/watch?v=123")[0], PlatformType.YOUTUBE)
        self.assertEqual(detect_platform("https://www.tiktok.com/@user/video/123")[0], PlatformType.TIKTOK)
        self.assertEqual(detect_platform("https://www.instagram.com/reel/123")[0], PlatformType.INSTAGRAM)
        self.assertEqual(detect_platform("https://x.com/user/status/123")[0], PlatformType.TWITTER)
        self.assertEqual(detect_platform("https://www.twitch.tv/videos/123")[0], PlatformType.TWITCH)
        self.assertEqual(detect_platform("https://stream.com/video.m3u8")[0], PlatformType.DIRECT_STREAM)


class TestConsoleUIAndErrorHandling(unittest.TestCase):
    def setUp(self):
        self.test_console = Console(file=StringIO(), force_terminal=False)

    def test_print_banner(self):
        print_banner(console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("Universal Video & Audio Downloader CLI", output)
        self.assertIn("1800+ sitios", output)

    def test_print_panels(self):
        print_success("Descarga exitosa", "video.mp4", console_instance=self.test_console)
        print_error("Fallo general", "detalles", console_instance=self.test_console)
        print_warning("Advertencia", "info", console_instance=self.test_console)
        print_info_panel("Información", "Título", console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("Descarga exitosa", output)
        self.assertIn("Fallo general", output)
        self.assertIn("Advertencia", output)
        self.assertIn("Información", output)

    def test_handle_download_error_instagram(self):
        err = Exception("HTTP Error 403: Forbidden - login required to view instagram reel")
        handle_download_error(err, context_url="https://www.instagram.com/reel/C8xyz123", console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("Instagram", output)
        self.assertIn("cookies_instagram.txt", output)

    def test_handle_download_error_twitter(self):
        err = Exception("This tweet contains sensitive media (NSFW) or requires login")
        handle_download_error(err, context_url="https://x.com/user/status/123456", console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("Twitter / X", output)
        self.assertIn("cookies_twitter.txt", output)

    def test_handle_download_error_tiktok(self):
        err = Exception("TikTok returned captcha / slide to verify challenge")
        handle_download_error(err, context_url="https://www.tiktok.com/@user/video/123", console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("TikTok", output)
        self.assertIn("cookies_tiktok.txt", output)

    def test_handle_download_error_twitch(self):
        err = Exception("This video is only available to subscribers (sub-only)")
        handle_download_error(err, context_url="https://www.twitch.tv/videos/123", console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("Twitch", output)
        self.assertIn("cookies_twitch.txt", output)

    def test_handle_download_error_youtube(self):
        err = Exception("HTTP Error 403: Forbidden - sign in to confirm you are not a bot (poToken required)")
        handle_download_error(err, context_url="https://www.youtube.com/watch?v=123", console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("YouTube", output)
        self.assertIn("cookies_youtube.txt", output)
        self.assertIn("Deno", output)

    def test_handle_download_error_direct_stream(self):
        err = Exception("HTTP Error 404: Not Found - manifest m3u8 expired token")
        handle_download_error(err, context_url="https://cdn.example.com/stream.m3u8", console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("Stream Directo", output)
        self.assertIn("m3u8", output)

    def test_handle_download_error_dpapi(self):
        err = Exception("Could not copy Chrome cookie database (dpapi failed to decrypt)")
        handle_download_error(err, console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("DPAPI", output)
        self.assertIn("Chromium", output)

    def test_handle_download_error_ffmpeg(self):
        err = Exception("ffmpeg is not installed or ffprobe not found in path")
        handle_download_error(err, console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("FFmpeg", output)
        self.assertIn("instalar_ffmpeg.bat", output)

    def test_handle_download_error_drm(self):
        err = Exception("This video is protected by DRM (Widevine encrypted stream)")
        handle_download_error(err, console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("DRM", output)

    def test_handle_download_error_geo(self):
        err = Exception("This video is not available in your region (geo-blocked)")
        handle_download_error(err, console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("geográfica", output)

    def test_handle_download_error_generic(self):
        err = Exception("Generic unknown network socket error")
        handle_download_error(err, console_instance=self.test_console)
        output = self.test_console.file.getvalue()
        self.assertIn("Error durante la descarga", output)


class TestUniversalNotifications(unittest.TestCase):
    def test_get_notification_title_video(self):
        self.assertEqual(get_notification_title(PlatformType.YOUTUBE), "🎬 YouTube Video Descargado")
        self.assertEqual(get_notification_title(PlatformType.TIKTOK), "🎵 TikTok Descargado")
        self.assertEqual(get_notification_title(PlatformType.INSTAGRAM), "📸 Instagram Reel Descargado")
        self.assertEqual(get_notification_title(PlatformType.TWITTER), "🐦 Twitter/X Video Descargado")
        self.assertEqual(get_notification_title(PlatformType.TWITCH), "🟣 Twitch VOD/Clip Descargado")
        self.assertEqual(get_notification_title(PlatformType.DIRECT_STREAM), "📡 Stream Directo Descargado")
        self.assertEqual(get_notification_title(PlatformType.GENERIC), "🌐 Video Web Descargado")

    def test_get_notification_title_audio(self):
        self.assertEqual(get_notification_title(PlatformType.YOUTUBE, audio_only=True), "🎵 YouTube Audio Guardado")
        self.assertEqual(get_notification_title(PlatformType.TIKTOK, audio_only=True), "🎵 TikTok Audio Guardado")
        self.assertEqual(get_notification_title(PlatformType.SOUNDCLOUD), "☁️ SoundCloud Audio Descargado")
        self.assertEqual(get_notification_title(PlatformType.BANDCAMP), "🎸 Bandcamp Audio Descargado")
        self.assertEqual(get_notification_title(PlatformType.DIRECT_STREAM, audio_only=True), "📡 Stream de Audio Guardado")

    def test_get_notification_title_playlist(self):
        self.assertEqual(get_notification_title(PlatformType.YOUTUBE, is_playlist=True), "📋 YouTube Playlist Completada")
        self.assertEqual(get_notification_title(PlatformType.TIKTOK, is_playlist=True), "🎵 TikTok Perfil/Lista Completada")
        self.assertEqual(get_notification_title(PlatformType.SOUNDCLOUD, is_playlist=True), "☁️ SoundCloud Set/Álbum Completado")
        self.assertEqual(get_notification_title(PlatformType.BANDCAMP, is_playlist=True), "🎸 Bandcamp Álbum Completado")

    def test_get_notification_title_batch(self):
        self.assertEqual(get_notification_title(PlatformType.GENERIC, is_batch=True), "📦 Lote Concurrente Universal Finalizado")

    def test_get_notification_title_from_url_string(self):
        self.assertEqual(get_notification_title("https://www.tiktok.com/@user/video/123"), "🎵 TikTok Descargado")
        self.assertEqual(get_notification_title("https://soundcloud.com/artist/track"), "☁️ SoundCloud Audio Descargado")

    def test_show_desktop_notification_fallback(self):
        # Debe retornar False o True de forma segura sin excepciones
        result = show_desktop_notification("Test Title", "Test Message", folder_path=Path("."))
        self.assertIsInstance(result, bool)


class TestUniversalProgressClassification(unittest.TestCase):
    def test_clean_stream_title(self):
        self.assertEqual(clean_stream_title("Video Title.f137.mp4.part"), "Video Title")
        self.assertEqual(clean_stream_title("Audio Track.f140.m4a.temp"), "Audio Track")
        self.assertEqual(clean_stream_title("My Song.opus", info_dict={'title': 'Explicit Song Title'}), "Explicit Song Title")

    def test_classify_stream_label_audio(self):
        self.assertIn("🎵", classify_stream_label("track.mp3"))
        self.assertIn("🎵", classify_stream_label("track.m4a"))
        self.assertIn("🎵", classify_stream_label("track.opus"))
        self.assertIn("🎵", classify_stream_label("track.flac"))
        self.assertIn("Audio", classify_stream_label("file.audio.part"))

    def test_classify_stream_label_video(self):
        self.assertIn("🎬", classify_stream_label("video.mp4"))
        self.assertIn("🎬", classify_stream_label("video.webm"))
        self.assertIn("🎬", classify_stream_label("video.mkv"))
        self.assertIn("Video", classify_stream_label("file.video.temp"))

    def test_classify_stream_label_subtitles(self):
        self.assertIn("📝", classify_stream_label("subtitles.vtt"))
        self.assertIn("📝", classify_stream_label("subtitles.srt"))
        self.assertIn("Subtítulo", classify_stream_label("subtitles.ttml"))

    def test_classify_stream_label_direct_stream(self):
        self.assertIn("📡", classify_stream_label("manifest.m3u8"))
        self.assertIn("📡", classify_stream_label("manifest.mpd"))
        self.assertIn("📡", classify_stream_label("chunk_01.ts"))
        self.assertIn("Stream", classify_stream_label("frag-123.m4s"))

    def test_get_postprocessor_label(self):
        self.assertIn("audio", get_postprocessor_label("FFmpegExtractAudio").lower())
        self.assertIn("combinando", get_postprocessor_label("Merger").lower())
        self.assertIn("carátula", get_postprocessor_label("EmbedThumbnail").lower())
        self.assertIn("subtítulos", get_postprocessor_label("EmbedSubtitle").lower())
        self.assertIn("metadatos", get_postprocessor_label("FFmpegMetadata").lower())


class TestProgressManagers(unittest.TestCase):
    def test_quiet_logger(self):
        logger = YtDlpQuietLogger()
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
        self.assertIn("warning message", logger.warnings)
        self.assertIn("error message", logger.errors)

    def test_single_progress_hook(self):
        mgr = RichDownloadProgress()
        mgr.hook({'status': 'downloading', 'filename': 'test.f137.mp4', 'total_bytes': 1000, 'downloaded_bytes': 500})
        mgr.hook({'status': 'finished', 'total_bytes': 1000})
        mgr.postprocessor_hook({'status': 'started', 'postprocessor': 'Merger'})
        mgr.postprocessor_hook({'status': 'finished', 'postprocessor': 'Merger'})

    def test_playlist_progress(self):
        mgr = RichPlaylistProgress()
        mgr.setup(5, "Mi Playlist")
        mgr.advance_overall(1)
        mgr.hook({'status': 'downloading', 'filename': 'test.mp4', 'total_bytes': 2000, 'downloaded_bytes': 1000})
        mgr.hook({'status': 'finished', 'total_bytes': 2000})

    def test_concurrent_batch_progress(self):
        mgr = RichConcurrentBatchProgress()
        mgr.setup(10, "Lote de Prueba")
        mgr.advance_overall(1)
        prog_hook, pp_hook, cleanup = mgr.create_hooks_for_item(1, 10, worker_id=1)
        prog_hook({'status': 'downloading', 'filename': 'video1.mp4', 'total_bytes': 1000, 'downloaded_bytes': 500})
        pp_hook({'status': 'started', 'postprocessor': 'ExtractAudio'})
        prog_hook({'status': 'finished', 'total_bytes': 1000})
        cleanup()


class TestCookies(unittest.TestCase):
    def test_get_cookie_opts_empty(self):
        with patch.object(Path, 'exists', return_value=False):
            opts = get_cookie_opts()
            self.assertEqual(opts, {})

    def test_get_cookie_opts_explicit_browser(self):
        opts_browser = get_cookie_opts(cookies_from='firefox')
        self.assertEqual(opts_browser.get('cookiesfrombrowser'), ('firefox', None, None, None))

    def test_get_cookie_opts_browser_positional(self):
        opts_browser = get_cookie_opts('brave')
        self.assertEqual(opts_browser.get('cookiesfrombrowser'), ('brave', None, None, None))

    def test_get_cookie_opts_explicit_file(self):
        with patch.object(Path, 'exists', return_value=True):
            opts = get_cookie_opts(cookies_file='custom_cookies.txt')
            self.assertIn('cookiefile', opts)
            self.assertTrue(opts['cookiefile'].endswith('custom_cookies.txt'))

    def test_get_cookie_opts_platform_specific_instagram(self):
        def fake_exists(self_path):
            return self_path.name == 'cookies_instagram.txt'

        with patch.object(Path, 'exists', side_effect=fake_exists, autospec=True):
            opts = get_cookie_opts(url="https://www.instagram.com/reel/C8xyz123")
            self.assertIn('cookiefile', opts)
            self.assertTrue(opts['cookiefile'].endswith('cookies_instagram.txt'))

    def test_get_cookie_opts_platform_specific_tiktok(self):
        def fake_exists(self_path):
            return self_path.name == 'cookies_tiktok.txt'

        with patch.object(Path, 'exists', side_effect=fake_exists, autospec=True):
            opts = get_cookie_opts(url="https://www.tiktok.com/@user/video/789123")
            self.assertIn('cookiefile', opts)
            self.assertTrue(opts['cookiefile'].endswith('cookies_tiktok.txt'))

    def test_get_cookie_opts_platform_specific_twitter(self):
        def fake_exists(self_path):
            return self_path.name == 'cookies_twitter.txt'

        with patch.object(Path, 'exists', side_effect=fake_exists, autospec=True):
            opts = get_cookie_opts(url="https://x.com/user/status/123456789")
            self.assertIn('cookiefile', opts)
            self.assertTrue(opts['cookiefile'].endswith('cookies_twitter.txt'))

    def test_get_cookie_opts_platform_direct_twitch(self):
        def fake_exists(self_path):
            return self_path.name == 'cookies_twitch.txt'

        with patch.object(Path, 'exists', side_effect=fake_exists, autospec=True):
            opts = get_cookie_opts(platform=PlatformType.TWITCH)
            self.assertIn('cookiefile', opts)
            self.assertTrue(opts['cookiefile'].endswith('cookies_twitch.txt'))

    def test_get_cookie_opts_generic_fallback(self):
        def fake_exists(self_path):
            return self_path.name == 'cookies.txt'

        with patch.object(Path, 'exists', side_effect=fake_exists, autospec=True):
            opts = get_cookie_opts(url="https://www.instagram.com/reel/C8xyz123")
            self.assertIn('cookiefile', opts)
            self.assertTrue(opts['cookiefile'].endswith('cookies.txt'))

    def test_get_cookie_opts_legacy_youtube_fallback(self):
        def fake_exists(self_path):
            return self_path.name == 'youtube_cookies.txt'

        with patch.object(Path, 'exists', side_effect=fake_exists, autospec=True):
            opts = get_cookie_opts(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            self.assertIn('cookiefile', opts)
            self.assertTrue(opts['cookiefile'].endswith('youtube_cookies.txt'))

    def test_find_cookie_file(self):
        def fake_exists(self_path):
            return str(self_path).replace('\\', '/').endswith('cookies/cookies_instagram.txt')

        with patch.object(Path, 'exists', side_effect=fake_exists, autospec=True):
            found = find_cookie_file('cookies_instagram.txt')
            self.assertIsNotNone(found)
            self.assertTrue(str(found).replace('\\', '/').endswith('cookies/cookies_instagram.txt'))

    def test_check_cookies_status(self):
        test_console = Console(file=StringIO(), force_terminal=False)
        check_cookies_status(console_instance=test_console)
        output = test_console.file.getvalue()
        self.assertIn("Diagnóstico Multi-Plataforma", output)
        self.assertIn("Archivos de Cookies", output)
        self.assertIn("Navegadores", output)


class TestUniversalDownloaderCore(unittest.TestCase):
    def setUp(self):
        self.downloader = UniversalDownloader(output_path="Descargas_Test")

    def test_class_aliases(self):
        self.assertIs(YouTubeDownloader, UniversalDownloader)
        self.assertIs(MediaDownloader, UniversalDownloader)
        yt_dl = YouTubeDownloader(output_path="Descargas_Test")
        self.assertIsInstance(yt_dl, UniversalDownloader)

    def test_init_paths_and_runtimes(self):
        self.assertTrue(self.downloader.output_path.exists())
        self.assertTrue(self.downloader.videos_path.exists())
        self.assertTrue(self.downloader.audios_path.exists())
        self.assertIsInstance(self.downloader.js_runtimes, dict)

    def test_extractor_args_dynamic(self):
        yt_args = self.downloader._get_extractor_args(PlatformType.YOUTUBE)
        self.assertIn('youtube', yt_args)
        self.assertIn('player_client', yt_args['youtube'])

        tt_args = self.downloader._get_extractor_args(PlatformType.TIKTOK)
        self.assertIn('tiktok', tt_args)

        ig_args = self.downloader._get_extractor_args(PlatformType.INSTAGRAM)
        self.assertEqual(ig_args, {})

        tw_args = self.downloader._get_extractor_args(PlatformType.TWITTER)
        self.assertEqual(tw_args, {})

        sc_args = self.downloader._get_extractor_args(PlatformType.SOUNDCLOUD)
        self.assertEqual(sc_args, {})

    def test_adaptive_format_strings(self):
        # Audio
        self.assertEqual(self.downloader._get_format_string('1080', audio_only=True), 'bestaudio/best')

        # Plataformas con streams progresivos (TikTok, Instagram, Twitter, Direct Stream)
        tt_fmt = self.downloader._get_format_string('1080', audio_only=False, platform=PlatformType.TIKTOK)
        self.assertEqual(tt_fmt, 'b[height<=1080]/best/b')

        ig_fmt = self.downloader._get_format_string('best', audio_only=False, platform=PlatformType.INSTAGRAM)
        self.assertEqual(ig_fmt, 'b/best')

        tw_fmt = self.downloader._get_format_string('720', audio_only=False, platform=PlatformType.TWITTER)
        self.assertEqual(tw_fmt, 'b[height<=720]/best/b')

        ds_fmt = self.downloader._get_format_string('best', audio_only=False, platform=PlatformType.DIRECT_STREAM)
        self.assertEqual(ds_fmt, 'b/best')

        # Plataformas con streams separados (YouTube, Twitch, Vimeo, Generic)
        yt_fmt = self.downloader._get_format_string('1080', audio_only=False, allow_merge=True, platform=PlatformType.YOUTUBE)
        self.assertEqual(yt_fmt, 'bv*[height<=1080]+ba/b[height<=1080]/best')

        yt_best = self.downloader._get_format_string('best', audio_only=False, allow_merge=True, platform=PlatformType.YOUTUBE)
        self.assertEqual(yt_best, 'bv*+ba/b/best')

        yt_nomerge = self.downloader._get_format_string('720', audio_only=False, allow_merge=False, platform=PlatformType.YOUTUBE)
        self.assertEqual(yt_nomerge, 'b[height<=720]/best/b')

    def test_audio_postprocessors(self):
        pps = self.downloader._get_audio_postprocessors('mp3', '320', embed_thumbnail=True)
        keys = [p['key'] for p in pps]
        self.assertIn('FFmpegExtractAudio', keys)
        self.assertIn('FFmpegMetadata', keys)
        self.assertIn('EmbedThumbnail', keys)

        pps_flac = self.downloader._get_audio_postprocessors('flac', '320', embed_thumbnail=True)
        self.assertEqual(pps_flac[0]['preferredcodec'], 'flac')

    def tearDown(self):
        import shutil
        if Path("Descargas_Test").exists():
            shutil.rmtree("Descargas_Test", ignore_errors=True)


    def test_get_target_folder_organization(self):
        # 1. Por defecto organiza por plataforma (organize_by_platform=True)
        self.assertTrue(self.downloader.organize_by_platform)

        # YouTube -> Videos/YouTube y Audios/YouTube
        f_yt_video = self.downloader._get_target_folder(audio_only=False, platform=PlatformType.YOUTUBE)
        self.assertEqual(f_yt_video, self.downloader.videos_path / "YouTube")

        f_yt_audio = self.downloader._get_target_folder(audio_only=True, platform=PlatformType.YOUTUBE)
        self.assertEqual(f_yt_audio, self.downloader.audios_path / "YouTube")

        # Twitch -> Videos/Twitch
        f_twitch = self.downloader._get_target_folder(audio_only=False, platform=PlatformType.TWITCH)
        self.assertEqual(f_twitch, self.downloader.videos_path / "Twitch")

        # TikTok -> Videos/TikTok
        f_tt = self.downloader._get_target_folder(audio_only=False, platform=PlatformType.TIKTOK)
        self.assertEqual(f_tt, self.downloader.videos_path / "TikTok")

        # SoundCloud -> Audios/SoundCloud
        f_sc = self.downloader._get_target_folder(audio_only=True, platform=PlatformType.SOUNDCLOUD)
        self.assertEqual(f_sc, self.downloader.audios_path / "SoundCloud")

        # Bandcamp -> Audios/Bandcamp
        f_bc = self.downloader._get_target_folder(audio_only=True, platform=PlatformType.BANDCAMP)
        self.assertEqual(f_bc, self.downloader.audios_path / "Bandcamp")

        # Generic y Direct Stream -> Videos/Otros y Audios/Otros
        f_gen = self.downloader._get_target_folder(audio_only=False, platform=PlatformType.GENERIC)
        self.assertEqual(f_gen, self.downloader.videos_path / "Otros")

        f_ds = self.downloader._get_target_folder(audio_only=True, platform=PlatformType.DIRECT_STREAM)
        self.assertEqual(f_ds, self.downloader.audios_path / "Otros")

        # Platform None -> Otros
        f_none = self.downloader._get_target_folder(audio_only=False, platform=None)
        self.assertEqual(f_none, self.downloader.videos_path / "Otros")

        # 2. Con organize_by_platform=False -> Videos y Audios (sin subcarpetas)
        dl_no_org = UniversalDownloader(output_path="Descargas_Test", organize_by_platform=False)
        self.assertFalse(dl_no_org.organize_by_platform)

        f_no_org_vid = dl_no_org._get_target_folder(audio_only=False, platform=PlatformType.YOUTUBE)
        self.assertEqual(f_no_org_vid, dl_no_org.videos_path)

        f_no_org_aud = dl_no_org._get_target_folder(audio_only=True, platform=PlatformType.SOUNDCLOUD)
        self.assertEqual(f_no_org_aud, dl_no_org.audios_path)

        # 3. Con override explícito por llamada
        f_override_false = self.downloader._get_target_folder(audio_only=False, platform=PlatformType.INSTAGRAM, organize_by_platform=False)
        self.assertEqual(f_override_false, self.downloader.videos_path)

        f_override_true = dl_no_org._get_target_folder(audio_only=False, platform=PlatformType.INSTAGRAM, organize_by_platform=True)
        self.assertEqual(f_override_true, dl_no_org.videos_path / "Instagram")

    def test_playlist_target_folder_organization(self):
        # Con organize_by_platform=True (default)
        target_base = self.downloader._get_target_folder(audio_only=False, platform=PlatformType.YOUTUBE)
        playlist_folder = target_base / "Mi Playlist"
        self.assertEqual(playlist_folder, self.downloader.videos_path / "YouTube" / "Mi Playlist")

        target_base_audio = self.downloader._get_target_folder(audio_only=True, platform=PlatformType.BANDCAMP)
        album_folder = target_base_audio / "Mi Album"
        self.assertEqual(album_folder, self.downloader.audios_path / "Bandcamp" / "Mi Album")

        # Con organize_by_platform=False
        target_base_no_org = self.downloader._get_target_folder(audio_only=False, platform=PlatformType.YOUTUBE, organize_by_platform=False)
        playlist_folder_no_org = target_base_no_org / "Mi Playlist"
        self.assertEqual(playlist_folder_no_org, self.downloader.videos_path / "Mi Playlist")



class TestExtractorUniversal(unittest.TestCase):
    def test_parse_format_dimensions(self):
        # Con height y width numéricos directos
        fmt1 = {'width': 1920, 'height': 1080, 'fps': 60}
        self.assertEqual(_parse_format_dimensions(fmt1), (1920, 1080, 60))

        # Con resolution en string (Twitch / HLS)
        fmt2 = {'resolution': '1280x720', 'format_note': '720p60'}
        self.assertEqual(_parse_format_dimensions(fmt2), (1280, 720, 60))

        # Con format_note (TikTok / HLS)
        fmt3 = {'format_note': '1080p'}
        self.assertEqual(_parse_format_dimensions(fmt3), (0, 1080, 0))

    @patch('core.extractor.yt_dlp.YoutubeDL')
    def test_get_video_and_media_info(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'id': 'abc123',
            'title': 'Test Reel TikTok',
            'uploader': 'test_user',
            'duration': 45,
            'view_count': 10000,
            'like_count': 500,
            'upload_date': '20260819',
            'formats': [
                {'format_id': '1', 'vcodec': 'h264', 'acodec': 'aac', 'height': 1080, 'fps': 30}
            ]
        }
        
        info = get_video_info("https://www.tiktok.com/@user/video/123456")
        self.assertIsNotNone(info)
        self.assertEqual(info['title'], 'Test Reel TikTok')
        self.assertEqual(info['platform'], PlatformType.TIKTOK)
        self.assertEqual(info['platform_name'], 'TikTok')
        self.assertFalse(info['is_audio_only'])

        # Comprobar alias get_media_info
        media_info = get_media_info("https://www.tiktok.com/@user/video/123456")
        self.assertEqual(media_info['id'], 'abc123')

    @patch('core.extractor.yt_dlp.YoutubeDL')
    def test_audio_only_platform_detection(self, mock_ydl_cls):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'id': 'sc123',
            'title': 'SoundCloud Track',
            'uploader': 'Music Artist',
            'duration': 180,
            'formats': [
                {'format_id': 'http_mp3', 'vcodec': 'none', 'acodec': 'mp3', 'abr': 128}
            ]
        }
        
        info = get_media_info("https://soundcloud.com/artist/track-name")
        self.assertIsNotNone(info)
        self.assertEqual(info['platform'], PlatformType.SOUNDCLOUD)
        self.assertTrue(info['is_audio_only'])

    @patch('rich.prompt.Prompt.ask')
    @patch('core.extractor.yt_dlp.YoutubeDL')
    def test_interactive_select_format_audio_only(self, mock_ydl_cls, mock_prompt):
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'id': 'sc123',
            'title': 'SoundCloud Track',
            'uploader': 'Music Artist',
            'duration': 180,
            'formats': [
                {'format_id': 'http_mp3', 'vcodec': 'none', 'acodec': 'mp3', 'abr': 128}
            ]
        }
        # Respuestas del prompt para formato (1=mp3) y bitrate (1=320)
        mock_prompt.side_effect = ["1", "1"]

        test_console = Console(file=StringIO(), force_terminal=False)
        result = interactive_select_format("https://soundcloud.com/artist/track", console_instance=test_console)
        self.assertIsNotNone(result)
        self.assertTrue(result['audio_only'])
        self.assertEqual(result['audio_format'], 'mp3')
        self.assertEqual(result['audio_quality'], '320')


class TestCLIEntrypoint(unittest.TestCase):
    def setUp(self):
        from click.testing import CliRunner
        self.runner = CliRunner()

    def test_cli_help(self):
        from youtube_downloader import cli
        result = self.runner.invoke(cli, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Universal Video & Audio Downloader", result.output)
        self.assertIn("download", result.output)
        self.assertIn("playlist", result.output)
        self.assertIn("batch", result.output)
        self.assertIn("info", result.output)
        self.assertIn("cookies", result.output)
        self.assertIn("clipboard", result.output)

    def test_download_help_organize_flag(self):
        from youtube_downloader import download
        result = self.runner.invoke(download, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--organize-by-platform", result.output)
        self.assertIn("--audio-format", result.output)
        self.assertIn("--audio-quality", result.output)

    def test_batch_help_organize_flag(self):
        from youtube_downloader import batch
        result = self.runner.invoke(batch, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--organize-by-platform", result.output)
        self.assertIn("--concurrency", result.output)

    def test_playlist_help_organize_flag(self):
        from youtube_downloader import playlist
        result = self.runner.invoke(playlist, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--organize-by-platform", result.output)
        self.assertIn("--start", result.output)


if __name__ == '__main__':
    unittest.main()
