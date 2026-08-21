"""
Test Suite para Resilient Playlist and Cookie Handling (REQ-01 a REQ-05).
Verifica:
1. REQ-01: Request pacing with randomized jitter (calculate_pacing_delay, zero-sleep, polite defaults).
2. REQ-02: YouTube player client rotation and fallback (extract_info_with_client_fallback, FALLBACK_PLAYER_CLIENTS).
3. REQ-03: Lock-safe Windows Chromium cookie extraction, profile parsing (parse_browser_spec, extract_cookies_lock_safe, get_available_browser_profiles).
4. REQ-04: Resilient playlist execution, per-item fault isolation, exponential backoff, abort-on-error, and Rich audit summary table.
5. REQ-05: Interactive recovery handler (prompt_interactive_recovery, TTY detection, live client/cookie switching).
6. Click CLI integration: option propagation for sleep-interval, max-sleep-interval, abort-on-error, interactive, and profile qualifiers.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from io import StringIO
from unittest.mock import MagicMock, patch, PropertyMock

from rich.console import Console
from click.testing import CliRunner

# Core modules
from core.cookies import (
    parse_browser_spec,
    get_available_browser_profiles,
    extract_cookies_lock_safe,
    get_cookie_opts,
    check_cookies_status,
    SUPPORTED_BROWSERS,
)
from core.extractor import (
    FALLBACK_PLAYER_CLIENTS,
    extract_info_with_client_fallback,
    get_raw_info,
    get_video_info,
)
from core.downloader import (
    UniversalDownloader,
    calculate_pacing_delay,
)
from ui.console import (
    prompt_interactive_recovery,
    handle_download_error,
)
from utils.platform_detector import PlatformType


class TestRequestPacing(unittest.TestCase):
    """Pruebas unitarias para el motor de request pacing y jitter (REQ-01)."""

    def test_pacing_configured_min_max(self):
        """S-01.1: Intervalo configurado con límites min y max."""
        for _ in range(50):
            delay = calculate_pacing_delay(sleep_interval=3.0, max_sleep_interval=7.0)
            self.assertGreaterEqual(delay, 3.0)
            self.assertLessEqual(delay, 7.0)

    def test_pacing_reversed_min_max(self):
        """Intervalo configurado con límites invertidos (max < min)."""
        for _ in range(50):
            delay = calculate_pacing_delay(sleep_interval=8.0, max_sleep_interval=4.0)
            self.assertGreaterEqual(delay, 4.0)
            self.assertLessEqual(delay, 8.0)

    def test_pacing_default_polite(self):
        """S-01.2: Comportamiento por defecto con pausa cortés 1.0s ± 0.5s."""
        for _ in range(50):
            delay = calculate_pacing_delay()
            self.assertGreaterEqual(delay, 0.5)
            self.assertLessEqual(delay, 1.5)

    def test_pacing_single_sleep_interval(self):
        """Intervalo único con jitter uniforme ±0.5s."""
        for _ in range(50):
            delay = calculate_pacing_delay(sleep_interval=2.0)
            self.assertGreaterEqual(delay, 1.5)
            self.assertLessEqual(delay, 2.5)

    def test_pacing_single_max_sleep_interval(self):
        """Intervalo con solo max_sleep_interval especificado."""
        for _ in range(50):
            delay = calculate_pacing_delay(max_sleep_interval=4.0)
            self.assertGreaterEqual(delay, 0.0)
            self.assertLessEqual(delay, 4.0)

    def test_pacing_zero_override(self):
        """S-01.3: Override explícito a 0 segundos."""
        self.assertEqual(calculate_pacing_delay(sleep_interval=0.0, max_sleep_interval=0.0), 0.0)
        self.assertEqual(calculate_pacing_delay(sleep_interval=0), 0.0)
        self.assertEqual(calculate_pacing_delay(max_sleep_interval=0), 0.0)

    def test_pacing_disabled_default(self):
        """Desactivación de pacing por defecto (default_pacing=False)."""
        self.assertEqual(calculate_pacing_delay(default_pacing=False), 0.0)


class TestLockSafeCookiesAndProfiles(unittest.TestCase):
    """Pruebas unitarias para extracción de cookies segura y perfiles de navegador (REQ-03)."""

    def test_parse_browser_spec_standard(self):
        """S-03.2: Parsea especificaciones de navegador con y sin perfil."""
        self.assertEqual(parse_browser_spec("brave"), ("brave", None))
        self.assertEqual(parse_browser_spec("brave:Default"), ("brave", "Default"))
        self.assertEqual(parse_browser_spec("chrome:Profile 1"), ("chrome", "Profile 1"))
        self.assertEqual(parse_browser_spec("edge:Profile 2"), ("edge", "Profile 2"))
        self.assertEqual(parse_browser_spec("firefox:default-release"), ("firefox", "default-release"))
        self.assertEqual(parse_browser_spec("  BRAVE : Profile 3  "), ("brave", "Profile 3"))

    def test_parse_browser_spec_edge_cases(self):
        """Casos borde para parse_browser_spec (vacíos, tipos incorrectos)."""
        self.assertEqual(parse_browser_spec(""), ("", None))
        self.assertEqual(parse_browser_spec(None), ("", None))
        self.assertEqual(parse_browser_spec("brave:"), ("brave", None))

    def test_get_cookie_opts_with_profile(self):
        """S-03.2: get_cookie_opts propaga el perfil a cookiesfrombrowser."""
        opts = get_cookie_opts(cookies_from="brave:Profile 1")
        self.assertEqual(opts.get('cookiesfrombrowser'), ("brave", "Profile 1", None, None))

        opts_default = get_cookie_opts(cookies_from="chrome:Default")
        self.assertEqual(opts_default.get('cookiesfrombrowser'), ("chrome", "Default", None, None))

        # Positional URL argument containing browser:profile
        opts_pos = get_cookie_opts(url="brave:Profile 2")
        self.assertEqual(opts_pos.get('cookiesfrombrowser'), ("brave", "Profile 2", None, None))

    @patch('core.cookies._get_chromium_user_data_path')
    def test_get_available_browser_profiles_discovery(self, mock_user_data_path):
        """Descubrimiento de perfiles múltiples en disco."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_data = Path(tmpdir)
            (user_data / "Default").mkdir()
            (user_data / "Profile 1").mkdir()
            (user_data / "Profile 2").mkdir()
            (user_data / "NotAProfile").mkdir()

            mock_user_data_path.return_value = user_data

            profiles = get_available_browser_profiles("chrome")
            self.assertIn("Default", profiles)
            self.assertIn("Profile 1", profiles)
            self.assertIn("Profile 2", profiles)
            self.assertNotIn("NotAProfile", profiles)

    @patch('core.cookies._get_chromium_user_data_path')
    def test_extract_cookies_lock_safe(self, mock_user_data_path):
        """S-03.1: Copia segura de la base de datos de cookies SQLite y Local State."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_data = Path(tmpdir)
            profile_dir = user_data / "Default"
            network_dir = profile_dir / "Network"
            network_dir.mkdir(parents=True)

            cookie_src = network_dir / "Cookies"
            cookie_src.write_bytes(b"SQLite format 3\x00MockCookieDBContent")

            local_state = user_data / "Local State"
            local_state.write_text('{"os_crypt":{"encrypted_key":"mock_key"}}', encoding="utf-8")

            mock_user_data_path.return_value = user_data

            temp_cookie_path = extract_cookies_lock_safe("brave", "Default")
            self.assertIsNotNone(temp_cookie_path)
            self.assertTrue(temp_cookie_path.exists())
            self.assertEqual(temp_cookie_path.read_bytes(), b"SQLite format 3\x00MockCookieDBContent")

            # Local State copied to the same temp directory
            temp_local_state = temp_cookie_path.parent / "Local State"
            self.assertTrue(temp_local_state.exists())

    def test_check_cookies_status_diagnostic(self):
        """S-03.3 & 1.3: Diagnóstico enriquecido con perfiles y App-Bound messaging."""
        test_console = Console(file=StringIO(), force_terminal=False)
        check_cookies_status(console_instance=test_console)
        output = test_console.file.getvalue()
        self.assertIn("Diagnóstico Multi-Plataforma de Cookies", output)
        self.assertIn("Estado de Sesiones en Navegadores Web", output)


class TestClientRotationAndFallback(unittest.TestCase):
    """Pruebas unitarias para rotación y fallback de clientes de reproducción (REQ-02)."""

    def test_fallback_player_clients_list(self):
        """Verifica la lista de clientes candidatos en rotación."""
        self.assertEqual(FALLBACK_PLAYER_CLIENTS, ['android', 'ios', 'mweb', 'tv_embedded', 'web'])

    @patch('yt_dlp.YoutubeDL')
    def test_client_rotation_success_on_second_client(self, mock_ydl_class):
        """S-02.1: Cliente 1 falla con 403, cliente 2 (ios) tiene éxito."""
        mock_instance1 = MagicMock()
        mock_instance1.extract_info.side_effect = Exception("HTTP Error 403: Forbidden - Bot detection")

        mock_instance2 = MagicMock()
        mock_instance2.extract_info.return_value = {
            'id': 'dQw4w9WgXcQ',
            'title': 'Test Video',
            'formats': [{'format_id': '18', 'ext': 'mp4'}]
        }

        mock_ydl_class.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=mock_instance1), __exit__=MagicMock(return_value=False)),
            MagicMock(__enter__=MagicMock(return_value=mock_instance2), __exit__=MagicMock(return_value=False)),
        ]

        test_console = Console(file=StringIO(), force_terminal=False)
        info, successful_client = extract_info_with_client_fallback(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            base_ydl_opts={'quiet': True},
            candidate_clients=['android', 'ios', 'mweb'],
            console_instance=test_console
        )

        self.assertIsNotNone(info)
        self.assertEqual(successful_client, 'ios')
        self.assertEqual(info.get('title'), 'Test Video')
        self.assertIn("Extracción recuperada con éxito usando cliente YouTube: 'ios'", test_console.file.getvalue())

    @patch('yt_dlp.YoutubeDL')
    def test_client_rotation_exhaustion(self, mock_ydl_class):
        """S-02.2: Todos los clientes candidatos fallan con 403."""
        mock_instance = MagicMock()
        mock_instance.extract_info.side_effect = Exception("HTTP Error 403: Forbidden poToken required")
        mock_ydl_class.return_value.__enter__.return_value = mock_instance

        test_console = Console(file=StringIO(), force_terminal=False)
        info, successful_client = extract_info_with_client_fallback(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            base_ydl_opts={'quiet': True},
            candidate_clients=['android', 'ios'],
            console_instance=test_console
        )

        self.assertIsNone(info)
        self.assertIsNone(successful_client)
        self.assertIn("Acceso bloqueado por YouTube", test_console.file.getvalue())

    @patch('yt_dlp.YoutubeDL')
    def test_non_youtube_direct_extraction(self, mock_ydl_class):
        """Plataformas no YouTube extraen directamente sin rotación de clientes."""
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {'title': 'Instagram Reel', 'id': '123'}
        mock_ydl_class.return_value.__enter__.return_value = mock_instance

        test_console = Console(file=StringIO(), force_terminal=False)
        info, successful_client = extract_info_with_client_fallback(
            url="https://www.instagram.com/reel/C8xyz123",
            base_ydl_opts={'quiet': True},
            console_instance=test_console
        )

        self.assertIsNotNone(info)
        self.assertIsNone(successful_client)
        self.assertEqual(info.get('title'), 'Instagram Reel')


class TestInteractiveRecoveryHandler(unittest.TestCase):
    """Pruebas unitarias para el menú interactivo de recuperación (REQ-05)."""

    def test_non_interactive_bypass(self):
        """S-05.3: Bypass automático cuando no es terminal TTY (sys.stdin.isatty() == False)."""
        with patch('sys.stdin.isatty', return_value=False):
            result = prompt_interactive_recovery("https://www.youtube.com/watch?v=123")
            self.assertIsNone(result)

    def test_interactive_choice_retry_client(self):
        """S-05.1: Selección de cambio de cliente de reproducción."""
        test_console = Console(file=StringIO(), force_terminal=True)
        with patch('sys.stdin.isatty', return_value=True):
            with patch('rich.prompt.Prompt.ask', side_effect=["1", "1"]):  # Choice 1 -> Client 1 (ios)
                result = prompt_interactive_recovery(
                    "https://www.youtube.com/watch?v=123",
                    failed_client="android",
                    console_instance=test_console
                )
                self.assertEqual(result, {'action': 'retry_client', 'client': 'ios'})

    def test_interactive_choice_retry_browser_cookies(self):
        """S-05.2: Selección de cambio de cookies de navegador."""
        test_console = Console(file=StringIO(), force_terminal=True)
        with patch('sys.stdin.isatty', return_value=True):
            with patch('rich.prompt.Prompt.ask', side_effect=["2", "1"]):  # Choice 2 -> Browser 1 (firefox)
                result = prompt_interactive_recovery(
                    "https://www.youtube.com/watch?v=123",
                    console_instance=test_console
                )
                self.assertEqual(result, {'action': 'retry_cookies_browser', 'browser': 'firefox'})

    def test_interactive_choice_skip_and_abort(self):
        """Selección de omitir (skip) y cancelar (abort)."""
        test_console = Console(file=StringIO(), force_terminal=True)
        with patch('sys.stdin.isatty', return_value=True):
            with patch('rich.prompt.Prompt.ask', return_value="4"):
                self.assertEqual(prompt_interactive_recovery("https://url", console_instance=test_console), {'action': 'skip'})

            with patch('rich.prompt.Prompt.ask', return_value="5"):
                self.assertEqual(prompt_interactive_recovery("https://url", console_instance=test_console), {'action': 'abort'})


class TestPlaylistResilienceAndAudit(unittest.TestCase):
    """Pruebas unitarias para tolerancia a fallos en playlists y tabla de auditoría (REQ-04)."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_console = Console(file=StringIO(), force_terminal=False)
        self.downloader = UniversalDownloader(
            output_path=self.test_dir.name,
            use_archive=False,
            console_instance=self.test_console
        )

    def tearDown(self):
        self.test_dir.cleanup()

    @patch('yt_dlp.YoutubeDL')
    def test_playlist_item_isolation_and_skip_errors(self, mock_ydl_class):
        """S-04.1: Error en elemento #2 no detiene la descarga de los elementos #1 y #3."""
        # Flat playlist con 3 elementos
        mock_flat_ydl = MagicMock()
        mock_flat_ydl.extract_info.return_value = {
            'title': 'Test Playlist',
            'entries': [
                {'id': 'vid1', 'title': 'Video 1', 'url': 'https://www.youtube.com/watch?v=vid1'},
                {'id': 'vid2', 'title': 'Video 2 (Private)', 'url': 'https://www.youtube.com/watch?v=vid2'},
                {'id': 'vid3', 'title': 'Video 3', 'url': 'https://www.youtube.com/watch?v=vid3'},
            ]
        }

        # Item downloads
        mock_item_ok1 = MagicMock()
        mock_item_fail2 = MagicMock()
        mock_item_fail2.download.side_effect = Exception("Private video or unavailable")
        mock_item_ok3 = MagicMock()

        mock_ydl_class.side_effect = [
            # Flat info extract
            MagicMock(__enter__=MagicMock(return_value=mock_flat_ydl), __exit__=MagicMock(return_value=False)),
            # Item 1: OK
            MagicMock(__enter__=MagicMock(return_value=mock_item_ok1), __exit__=MagicMock(return_value=False)),
            # Item 2: Fails
            MagicMock(__enter__=MagicMock(return_value=mock_item_fail2), __exit__=MagicMock(return_value=False)),
            # Item 3: OK
            MagicMock(__enter__=MagicMock(return_value=mock_item_ok3), __exit__=MagicMock(return_value=False)),
        ]

        with patch('time.sleep'):
            success = self.downloader.download_playlist(
                url="https://www.youtube.com/playlist?list=PL123",
                skip_errors=True,
                abort_on_error=False,
                sleep_interval=0,
                max_sleep_interval=0,
                max_retries=1
            )

        self.assertTrue(success)
        output = self.test_console.file.getvalue()
        # Audit summary table checks (S-04.3)
        self.assertIn("Resumen de Auditoría de Lista", output)
        self.assertIn("Video 1", output)
        self.assertIn("Video 2", output)
        self.assertIn("Video 3", output)
        self.assertIn("Guardados con éxito: 2 de 3", output)
        self.assertIn("Fallidos: 1", output)

    @patch('yt_dlp.YoutubeDL')
    def test_playlist_abort_on_error(self, mock_ydl_class):
        """S-04.4: Flag abort_on_error detiene la lista inmediatamente en el primer fallo."""
        mock_flat_ydl = MagicMock()
        mock_flat_ydl.extract_info.return_value = {
            'title': 'Test Playlist',
            'entries': [
                {'id': 'vid1', 'title': 'Video 1', 'url': 'https://www.youtube.com/watch?v=vid1'},
                {'id': 'vid2', 'title': 'Video 2 (Failing)', 'url': 'https://www.youtube.com/watch?v=vid2'},
                {'id': 'vid3', 'title': 'Video 3', 'url': 'https://www.youtube.com/watch?v=vid3'},
            ]
        }

        mock_item_ok1 = MagicMock()
        mock_item_fail2 = MagicMock()
        mock_item_fail2.download.side_effect = Exception("Critical Error")

        mock_ydl_class.side_effect = [
            # Flat info extract
            MagicMock(__enter__=MagicMock(return_value=mock_flat_ydl), __exit__=MagicMock(return_value=False)),
            # Item 1: OK
            MagicMock(__enter__=MagicMock(return_value=mock_item_ok1), __exit__=MagicMock(return_value=False)),
            # Item 2: Fails -> Should abort before item 3
            MagicMock(__enter__=MagicMock(return_value=mock_item_fail2), __exit__=MagicMock(return_value=False)),
        ]

        with patch('time.sleep'):
            self.downloader.download_playlist(
                url="https://www.youtube.com/playlist?list=PL123",
                skip_errors=False,
                abort_on_error=True,
                sleep_interval=0,
                max_sleep_interval=0,
                max_retries=1
            )

        output = self.test_console.file.getvalue()
        self.assertIn("Deteniendo lista tras fallo en elemento #2", output)
        self.assertNotIn("Video 3", output)


class TestCliOptionsIntegration(unittest.TestCase):
    """Pruebas de integración para nuevos flags y opciones en Click CLI."""

    def setUp(self):
        self.runner = CliRunner()

    def test_download_help_new_options(self):
        """Verifica que las opciones --sleep-interval, --max-sleep-interval e --interactive aparezcan en download --help."""
        from youtube_downloader import download
        result = self.runner.invoke(download, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--sleep-interval', result.output)
        self.assertIn('--max-sleep-interval', result.output)
        self.assertIn('--interactive', result.output)
        self.assertIn('--cookies-from', result.output)

    def test_playlist_help_new_options(self):
        """Verifica que las opciones --abort-on-error, --skip-errors y pacing aparezcan en playlist --help."""
        from youtube_downloader import playlist
        result = self.runner.invoke(playlist, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--abort-on-error', result.output)
        self.assertIn('--skip-errors', result.output)
        self.assertIn('--sleep-interval', result.output)
        self.assertIn('--max-sleep-interval', result.output)
        self.assertIn('--interactive', result.output)

    def test_batch_help_new_options(self):
        """Verifica que las opciones de pacing y abort aparezcan en batch --help."""
        from youtube_downloader import batch
        result = self.runner.invoke(batch, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--sleep-interval', result.output)
        self.assertIn('--max-sleep-interval', result.output)
        self.assertIn('--abort-on-error', result.output)


if __name__ == '__main__':
    unittest.main()
