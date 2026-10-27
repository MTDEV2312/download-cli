"""
Pruebas unitarias para la resolución inteligente de cookies y correcciones del descargador.
Verifica:
1. Inspección inteligente de cookies por dominio y tokens de autenticación clave (auth_token, sessionid, SAPISID/LOGIN_INFO vs guest_id).
2. Selección del candidato con mayor puntuación de autenticación y preservación del orden en empates.
3. Inclusión de cookies_x.txt en AUDIT_COOKIE_TARGETS y reporte de estado de sesión en check_cookies_status.
4. Sincronización de cookies/cookies_twitter.txt con sesión válida.
5. Diferenciación en UniversalDownloader entre clean download archive hit (retorna True) y fallo real de extracción (retorna False).
6. Recomendación de cookies_x.txt en ui/console.py ante errores de Twitter/X.
"""

import os
import tempfile
import unittest
from pathlib import Path
from io import StringIO
from unittest.mock import MagicMock, patch

from rich.console import Console

from core.cookies import (
    AUDIT_COOKIE_TARGETS,
    PLATFORM_COOKIE_FILES,
    PLATFORM_COOKIE_DOMAINS,
    PLATFORM_AUTH_TOKENS,
    inspect_cookie_file,
    find_cookie_file,
    get_cookie_opts,
    check_cookies_status,
)
from core.downloader import UniversalDownloader
from core.extractor import get_raw_info
from ui.console import handle_download_error
from utils.platform_detector import PlatformType


SAMPLE_KICK_AUTH_COOKIES = """# Netscape HTTP Cookie File
.kick.com	TRUE	/	TRUE	1806803394	cf_clearance	mock_cf_clearance_value
.kick.com	TRUE	/	TRUE	1806803391	session_token	mock_session_token_value
.kick.com	TRUE	/	TRUE	1806803392	kick_session	mock_kick_session_value
"""


SAMPLE_TWITTER_AUTH_COOKIES = """# Netscape HTTP Cookie File
.x.com	TRUE	/	TRUE	1806803394	guest_id	mock_guest_id_value
.x.com	TRUE	/	TRUE	1806803391	auth_token	mock_auth_token_value
.x.com	TRUE	/	TRUE	1806803392	ct0	mock_ct0_value
"""

SAMPLE_TWITTER_GUEST_COOKIES = """# Netscape HTTP Cookie File
.x.com	TRUE	/	TRUE	1854070902	guest_id	mock_guest_id_value
.x.com	TRUE	/	TRUE	1854070902	guest_id_marketing	mock_guest_id_value
"""

SAMPLE_TWITCH_COOKIES = """# Netscape HTTP Cookie File
.twitch.tv	TRUE	/	TRUE	1804567452	login	testuser
.twitch.tv	TRUE	/	TRUE	1804567452	auth-token	mock_twitch_auth_token
"""

SAMPLE_INSTAGRAM_AUTH_COOKIES = """# Netscape HTTP Cookie File
.instagram.com	TRUE	/	TRUE	1806803394	sessionid	mock_session_id_value
.instagram.com	TRUE	/	TRUE	1806803394	mid	mock_mid_value
"""

SAMPLE_YOUTUBE_AUTH_COOKIES = """# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	1806803394	LOGIN_INFO	mock_login_info_value
.youtube.com	TRUE	/	TRUE	1806803394	SAPISID	mock_sapisid_value
"""


class TestSmartCookieResolution(unittest.TestCase):
    """Pruebas de inspección y resolución inteligente de cookies multi-sitio."""

    def test_audit_cookie_targets_includes_cookies_x(self):
        """Verifica que AUDIT_COOKIE_TARGETS incluya cookies_x.txt para Twitter/X."""
        target_filenames = [t[0] for t in AUDIT_COOKIE_TARGETS]
        self.assertIn("cookies_x.txt", target_filenames)
        # Verificar que esté mapeado a PlatformType.TWITTER
        for fname, desc, p_type in AUDIT_COOKIE_TARGETS:
            if fname == "cookies_x.txt":
                self.assertEqual(p_type, PlatformType.TWITTER)

    def test_audit_cookie_targets_and_domains_include_kick(self):
        """Verifica que AUDIT_COOKIE_TARGETS y PLATFORM_COOKIE_DOMAINS incluyan kick.com."""
        target_filenames = [t[0] for t in AUDIT_COOKIE_TARGETS]
        self.assertIn("cookies_kick.txt", target_filenames)
        for fname, desc, p_type in AUDIT_COOKIE_TARGETS:
            if fname == "cookies_kick.txt":
                self.assertEqual(p_type, PlatformType.KICK)

        self.assertIn(PlatformType.KICK, PLATFORM_COOKIE_DOMAINS)
        name, domains = PLATFORM_COOKIE_DOMAINS[PlatformType.KICK]
        self.assertEqual(name, "Kick")
        self.assertIn("kick.com", domains)

    def test_inspect_cookie_file_kick_auth_token(self):
        """Verifica que un archivo con session_token de Kick obtenga alta puntuación y has_auth=True."""
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
            f.write(SAMPLE_KICK_AUTH_COOKIES)
            temp_path = Path(f.name)

        try:
            res = inspect_cookie_file(temp_path, platform=PlatformType.KICK)
            self.assertTrue(res['has_auth'])
            self.assertIn('session_token', res['auth_tokens_found'])
            self.assertGreaterEqual(res['score'], 1000)
            self.assertIn("session_token", res['status_label'])
        finally:
            temp_path.unlink(missing_ok=True)

    def test_inspect_cookie_file_twitter_auth_token(self):
        """Verifica que un archivo con auth_token obtenga alta puntuación y has_auth=True."""
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
            f.write(SAMPLE_TWITTER_AUTH_COOKIES)
            temp_path = Path(f.name)

        try:
            res = inspect_cookie_file(temp_path, platform=PlatformType.TWITTER)
            self.assertTrue(res['has_auth'])
            self.assertIn('auth_token', res['auth_tokens_found'])
            self.assertGreaterEqual(res['score'], 1000)
            self.assertIn("auth_token", res['status_label'])
        finally:
            temp_path.unlink(missing_ok=True)

    def test_inspect_cookie_file_twitter_guest_only(self):
        """Verifica que un archivo con solo guest_id obtenga has_auth=False y puntuación menor a 100."""
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
            f.write(SAMPLE_TWITTER_GUEST_COOKIES)
            temp_path = Path(f.name)

        try:
            res = inspect_cookie_file(temp_path, platform=PlatformType.TWITTER)
            self.assertFalse(res['has_auth'])
            self.assertTrue(res['has_guest'])
            self.assertIn('guest_id', res['guest_tokens_found'])
            self.assertLess(res['score'], 100)
            self.assertIn("Guest", res['status_label'])
        finally:
            temp_path.unlink(missing_ok=True)

    def test_inspect_cookie_file_wrong_domain_scores_zero(self):
        """Verifica que un archivo sin cookies del dominio objetivo obtenga puntuación 0."""
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
            f.write(SAMPLE_TWITCH_COOKIES)
            temp_path = Path(f.name)

        try:
            res = inspect_cookie_file(temp_path, platform=PlatformType.TWITTER)
            self.assertEqual(res['domain_cookies_count'], 0)
            self.assertEqual(res['score'], 0)
            self.assertIn("Sin cookies del dominio", res['status_label'])
        finally:
            temp_path.unlink(missing_ok=True)

    def test_inspect_cookie_file_instagram_auth(self):
        """Verifica detección de sessionid en Instagram."""
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
            f.write(SAMPLE_INSTAGRAM_AUTH_COOKIES)
            temp_path = Path(f.name)

        try:
            res = inspect_cookie_file(temp_path, platform=PlatformType.INSTAGRAM)
            self.assertTrue(res['has_auth'])
            self.assertIn('sessionid', res['auth_tokens_found'])
            self.assertGreaterEqual(res['score'], 1000)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_inspect_cookie_file_youtube_auth(self):
        """Verifica detección de SAPISID y LOGIN_INFO en YouTube."""
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
            f.write(SAMPLE_YOUTUBE_AUTH_COOKIES)
            temp_path = Path(f.name)

        try:
            res = inspect_cookie_file(temp_path, platform=PlatformType.YOUTUBE)
            self.assertTrue(res['has_auth'])
            self.assertGreaterEqual(res['score'], 1000)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_smart_resolution_selects_authenticated_over_guest(self):
        """Verifica que entre cookies_twitter.txt (guest) y cookies_x.txt (auth_token), se elija cookies_x.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_dir = Path(tmpdir) / "cookies"
            cookies_dir.mkdir()

            twitter_file = cookies_dir / "cookies_twitter.txt"
            x_file = cookies_dir / "cookies_x.txt"

            twitter_file.write_text(SAMPLE_TWITTER_GUEST_COOKIES, encoding='utf-8')
            x_file.write_text(SAMPLE_TWITTER_AUTH_COOKIES, encoding='utf-8')

            with patch('core.cookies.COOKIES_DIR', cookies_dir):
                opts = get_cookie_opts(url="https://x.com/user/status/123456789")
                self.assertIn('cookiefile', opts)
                self.assertTrue(opts['cookiefile'].endswith("cookies_x.txt"))

    def test_smart_resolution_preserves_fallback_order_on_equal_auth_scores(self):
        """Verifica que cuando ambos archivos tienen auth_token (empate), se conserve el orden de fallback estándar."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_dir = Path(tmpdir) / "cookies"
            cookies_dir.mkdir()

            twitter_file = cookies_dir / "cookies_twitter.txt"
            x_file = cookies_dir / "cookies_x.txt"

            # Ambos con tokens válidos de autenticación
            twitter_file.write_text(SAMPLE_TWITTER_AUTH_COOKIES, encoding='utf-8')
            x_file.write_text(SAMPLE_TWITTER_AUTH_COOKIES, encoding='utf-8')

            with patch('core.cookies.COOKIES_DIR', cookies_dir):
                opts = get_cookie_opts(url="https://x.com/user/status/123456789")
                self.assertIn('cookiefile', opts)
                # cookies_twitter.txt tiene mayor prioridad en PLATFORM_COOKIE_FILES que cookies_x.txt
                self.assertTrue(opts['cookiefile'].endswith("cookies_twitter.txt"))

    def test_smart_resolution_preserves_fallback_order_when_no_tokens(self):
        """Verifica que cuando ningún candidato tiene tokens, se conserve el orden de fallback estándar."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_dir = Path(tmpdir) / "cookies"
            cookies_dir.mkdir()

            twitter_file = cookies_dir / "cookies_twitter.txt"
            x_file = cookies_dir / "cookies_x.txt"

            twitter_file.write_text("# empty\n", encoding='utf-8')
            x_file.write_text("# empty\n", encoding='utf-8')

            with patch('core.cookies.COOKIES_DIR', cookies_dir):
                opts = get_cookie_opts(url="https://x.com/user/status/123456789")
                self.assertIn('cookiefile', opts)
                self.assertTrue(opts['cookiefile'].endswith("cookies_twitter.txt"))

    def test_find_cookie_file_with_platform(self):
        """Verifica que find_cookie_file resuelva con platform adecuadamente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_dir = Path(tmpdir) / "cookies"
            cookies_dir.mkdir()

            twitter_file = cookies_dir / "cookies_twitter.txt"
            x_file = cookies_dir / "cookies_x.txt"

            twitter_file.write_text(SAMPLE_TWITTER_GUEST_COOKIES, encoding='utf-8')
            x_file.write_text(SAMPLE_TWITTER_AUTH_COOKIES, encoding='utf-8')

            with patch('core.cookies.COOKIES_DIR', cookies_dir):
                found = find_cookie_file(platform=PlatformType.TWITTER)
                self.assertIsNotNone(found)
                self.assertTrue(str(found).endswith("cookies_x.txt"))

    def test_check_cookies_status_reports_active_session(self):
        """Verifica que check_cookies_status reporte Sesión Activa cuando hay auth_token."""
        test_console = Console(file=StringIO(), force_terminal=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            cookies_dir = Path(tmpdir) / "cookies"
            cookies_dir.mkdir()
            (cookies_dir / "cookies_x.txt").write_text(SAMPLE_TWITTER_AUTH_COOKIES, encoding='utf-8')

            with patch('core.cookies.COOKIES_DIR', cookies_dir):
                check_cookies_status(console_instance=test_console)
                output = test_console.file.getvalue()
                self.assertIn("cookies_x.txt", output)
                self.assertIn("Sesión Activa", output)


class TestCookiesTwitterFileSync(unittest.TestCase):
    """Verifica que el archivo real cookies/cookies_twitter.txt tenga credenciales válidas sincronizadas."""

    def test_cookies_twitter_contains_valid_auth_token(self):
        twitter_path = Path("cookies/cookies_twitter.txt")
        if not twitter_path.exists():
            self.skipTest("Local cookies_twitter.txt not present")
        content = twitter_path.read_text(encoding='utf-8', errors='ignore')
        self.assertIn("auth_token", content)
        self.assertIn("ct0", content)


class TestDownloaderExtractionAndArchive(unittest.TestCase):
    """Verifica las correcciones en UniversalDownloader sobre extracción y archive hits."""

    def setUp(self):
        self.downloader = UniversalDownloader(output_path="Descargas_Test")

    def test_extract_possible_ids_from_url(self):
        """Verifica extracción de IDs de medios desde URLs conocidas."""
        # Twitter / X
        ids_tw = self.downloader._extract_possible_ids_from_url("https://x.com/user/status/2089773556271824896")
        self.assertIn("2089773556271824896", ids_tw)

        # YouTube
        ids_yt = self.downloader._extract_possible_ids_from_url("https://www.youtube.com/watch?v=hsXeFqj5p7Q")
        self.assertIn("hsXeFqj5p7Q", ids_yt)

        # Instagram
        ids_ig = self.downloader._extract_possible_ids_from_url("https://www.instagram.com/reel/C8xyz123/")
        self.assertIn("C8xyz123", ids_ig)

        # TikTok
        ids_tt = self.downloader._extract_possible_ids_from_url("https://www.tiktok.com/@user/video/7123456789012345678")
        self.assertIn("7123456789012345678", ids_tt)

        # Twitch
        ids_twitch = self.downloader._extract_possible_ids_from_url("https://www.twitch.tv/videos/2848369758")
        self.assertTrue("2848369758" in ids_twitch or "v2848369758" in ids_twitch)

        # Kick
        ids_kick_vod = self.downloader._extract_possible_ids_from_url("https://kick.com/streamer/videos/5c697a87-afce-4256-b01f-3c8fe71ef5cb")
        self.assertIn("5c697a87-afce-4256-b01f-3c8fe71ef5cb", ids_kick_vod)

        ids_kick_clip = self.downloader._extract_possible_ids_from_url("https://kick.com/streamer?clip=clip_01GYXVB5Y8PWAPWCWMSBCFB05X")
        self.assertIn("clip_01GYXVB5Y8PWAPWCWMSBCFB05X", ids_kick_clip)

    def test_is_in_download_archive(self):
        """Verifica comprobación de ID en download archive."""
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
            f.write("twitter 2089773556271824896\n")
            f.write("youtube hsXeFqj5p7Q\n")
            archive_path = Path(f.name)

        try:
            self.downloader.archive_file = archive_path
            # URL que coincide con Twitter
            self.assertTrue(self.downloader._is_in_download_archive("https://x.com/user/status/2089773556271824896"))
            # URL que coincide con YouTube
            self.assertTrue(self.downloader._is_in_download_archive("https://www.youtube.com/watch?v=hsXeFqj5p7Q"))
            # URL no presente en el archivo
            self.assertFalse(self.downloader._is_in_download_archive("https://x.com/user/status/9999999999999999999"))
        finally:
            archive_path.unlink(missing_ok=True)

    def test_download_video_clean_archive_hit_returns_true(self):
        """Verifica que si info es None pero el item está en el archivo de descargas, retorne True."""
        url = "https://x.com/user/status/2089773556271824896"
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
            f.write("twitter 2089773556271824896\n")
            archive_path = Path(f.name)

        try:
            self.downloader.archive_file = archive_path
            self.downloader.use_archive = True

            with patch('core.downloader.extract_info_with_client_fallback', return_value=(None, None)):
                result = self.downloader.download_video(url, use_archive=True)
                self.assertTrue(result)
        finally:
            archive_path.unlink(missing_ok=True)

    def test_download_video_extraction_failure_returns_false(self):
        """Verifica que si info es None y NO está en el archive, retorne False (fallo real)."""
        url = "https://x.com/user/status/9999999999999999999"
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt') as f:
            f.write("twitter 2089773556271824896\n")
            archive_path = Path(f.name)

        try:
            self.downloader.archive_file = archive_path
            self.downloader.use_archive = True

            with patch('core.downloader.extract_info_with_client_fallback', return_value=(None, None)):
                result = self.downloader.download_video(url, use_archive=True)
                self.assertFalse(result)
        finally:
            archive_path.unlink(missing_ok=True)


class TestUIConsoleRecommendations(unittest.TestCase):
    """Verifica recomendaciones en ui/console.py."""

    def test_twitter_error_recommends_cookies_x(self):
        """Verifica que ante un error en Twitter/X se sugiera cookies_x.txt."""
        test_console = Console(file=StringIO(), force_terminal=False)
        fake_err = Exception("Twitter: User not found / restricted")
        handle_download_error(fake_err, "https://x.com/user/status/123", console_instance=test_console)
        output = test_console.file.getvalue()
        self.assertIn("cookies_x.txt", output)
        self.assertIn("cookies_twitter.txt", output)

    def test_kick_error_recommends_cookies_kick(self):
        """Verifica que ante un error en Kick se sugiera cookies_kick.txt."""
        test_console = Console(file=StringIO(), force_terminal=False)
        fake_err = Exception("Kick: Cloudflare verification or mature content")
        handle_download_error(fake_err, "https://kick.com/streamer", console_instance=test_console)
        output = test_console.file.getvalue()
        self.assertIn("cookies_kick.txt", output)
        self.assertIn("Kick", output)


class TestKickVODExtraction(unittest.TestCase):
    """Verifica el parche defensivo de KickVODIE para streams Next.js HLS (AWS IVS)."""

    def test_kick_vod_patch_extracts_recording_url(self):
        from yt_dlp.extractor.kick import KickVODIE
        from yt_dlp.utils import ExtractorError

        vod_ie = KickVODIE()
        sample_html = (
            '<html><head>'
            '<meta property="og:title" content="TORNEO DE STREAMERS - streamer VOD on KICK"/>'
            '<meta property="og:description" content="Gran final en vivo"/>'
            '<meta property="og:image" content="https://web.kick.com/api/v1/videos/1234/thumb.jpg"/>'
            '</head><body>'
            '\\"channel\\":{\\"id\\":999,\\"slug\\":\\"streamer\\",\\"username\\":\\"streamer\\"},'
            '\\"duration\\":3600,\\"end_time\\":\\"2026-10-26T00:00:00Z\\",'
            '\\"recording_url\\":\\"https://stream.kick.com/mock/master.m3u8\\"'
            '</body></html>'
        )

        with patch.object(vod_ie, '_download_webpage', return_value=sample_html):
            with patch.object(vod_ie, '_extract_m3u8_formats', return_value=[{'format_id': '1080p', 'url': 'mock.m3u8'}]):
                info = vod_ie._real_extract('https://kick.com/streamer/videos/01a175bc-8eb0-72a9-b3d3-daab1ad078f3')
                self.assertEqual(info['id'], '01a175bc-8eb0-72a9-b3d3-daab1ad078f3')
                self.assertEqual(info['title'], 'TORNEO DE STREAMERS')
                self.assertEqual(info['uploader'], 'streamer')
                self.assertEqual(info['duration'], 3600)
                self.assertEqual(len(info['formats']), 1)

    def test_kick_vod_patch_raises_sub_only_when_no_recording_url(self):
        from yt_dlp.extractor.kick import KickVODIE
        from yt_dlp.utils import ExtractorError

        vod_ie = KickVODIE()
        sample_html = (
            '<html><head><title>Sub only stream</title></head><body>'
            '\\"channel\\":{\\"id\\":999,\\"slug\\":\\"streamer\\",\\"username\\":\\"streamer\\"},'
            '\\"duration\\":3600,\\"status\\":\\"sub_only\\"'
            '</body></html>'
        )

        with patch.object(vod_ie, '_download_webpage', return_value=sample_html):
            with self.assertRaises(ExtractorError) as ctx:
                vod_ie._real_extract('https://kick.com/streamer/videos/01a175bc-8eb0-72a9-b3d3-daab1ad078f3')
            self.assertIn("sub_only", str(ctx.exception))
            self.assertIn("cookies/cookies_kick.txt", str(ctx.exception))


class TestCookielessFirstStrategy(unittest.TestCase):
    """Verifica que todas las descargas intenten primero sin cookies y usen cookies solo como fallback."""

    def test_get_raw_info_tries_clean_first_then_cookie_fallback(self):
        """get_raw_info primero intenta sin cookies; si falla, reintenta con cookies."""
        url = "https://kick.com/streamer/videos/12345"
        mock_info = {'title': 'Kick VOD', 'id': '12345', 'entries': []}

        # Simular: intento 1 (sin cookies) -> (None, None); intento 2 (con cookies) -> (mock_info, None)
        with patch('core.extractor.extract_info_with_client_fallback', side_effect=[(None, None), (mock_info, None)]) as mock_extract:
            with patch('core.extractor.get_cookie_opts', return_value={'cookiefile': 'cookies/cookies_kick.txt'}):
                info = get_raw_info(url)
                self.assertIsNotNone(info)
                self.assertTrue(info.get('_used_cookies'))
                self.assertEqual(mock_extract.call_count, 2)
                # La primera llamada debió ser sin cookiefile
                first_opts = mock_extract.call_args_list[0][1]['base_ydl_opts']
                self.assertNotIn('cookiefile', first_opts)
                # La segunda llamada debió incluir cookiefile
                second_opts = mock_extract.call_args_list[1][1]['base_ydl_opts']
                self.assertIn('cookiefile', second_opts)

    def test_download_video_tries_clean_first_then_cookie_fallback(self):
        """download_video primero intenta sin cookies; si falla, reintenta con cookies."""
        url = "https://www.youtube.com/watch?v=mock123"
        downloader = UniversalDownloader(output_path="Descargas_Test")
        mock_info = {
            'id': 'mock123',
            'title': 'Test Video',
            'duration': 60,
            'entries': [{'id': 'mock123', 'title': 'Test Video', 'duration': 60}],
            'formats': [{'format_id': '18', 'ext': 'mp4'}]
        }

        with patch('core.downloader.extract_info_with_client_fallback', side_effect=[(None, None), (mock_info, 'ios')]) as mock_extract:
            with patch.object(downloader, '_get_cookie_opts', return_value={'cookiefile': 'cookies/cookies_youtube.txt'}):
                with patch('yt_dlp.YoutubeDL'):
                    success = downloader.download_video(url, use_archive=False, notify=False)
                    self.assertTrue(success)
                    self.assertEqual(mock_extract.call_count, 2)
                    first_opts = mock_extract.call_args_list[0][1]['base_ydl_opts']
                    self.assertNotIn('cookiefile', first_opts)
                    second_opts = mock_extract.call_args_list[1][1]['base_ydl_opts']
                    self.assertIn('cookiefile', second_opts)


if __name__ == '__main__':
    unittest.main()
