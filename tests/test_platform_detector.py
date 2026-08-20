"""
Test Suite para el módulo de Detección Dinámica de Plataformas y Portapapeles Universal (Fase 1).
Verifica:
1. utils.platform_detector: PlatformType, PlatformInfo, is_valid_url, get_platform_info, detect_platform.
2. utils.clipboard: get_clipboard_url, resolve_url, is_youtube_url, compatibilidad retrocompatible.
"""

import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
from rich.console import Console

from utils.platform_detector import (
    PlatformType,
    PlatformInfo,
    PLATFORM_METADATA,
    PLATFORM_FOLDER_NAMES,
    get_platform_folder_name,
    is_valid_url,
    is_valid_media_url,
    get_platform_info,
    detect_platform,
)
from utils.clipboard import (
    YOUTUBE_REGEX,
    is_youtube_url,
    get_clipboard_url,
    resolve_url,
)


class TestPlatformDetector(unittest.TestCase):
    def test_is_valid_url_valid_cases(self):
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtu.be/dQw4w9WgXcQ",
            "https://www.tiktok.com/@user/video/1234567890",
            "https://www.instagram.com/reel/C123456789/",
            "https://x.com/user/status/123456789",
            "https://twitter.com/user/status/123456789",
            "https://www.twitch.tv/videos/123456789",
            "https://fb.watch/123456/",
            "https://www.facebook.com/watch/?v=123456",
            "https://v.redd.it/123456789",
            "https://soundcloud.com/artist/track-name",
            "https://artist.bandcamp.com/track/song",
            "https://vimeo.com/123456789",
            "https://kick.com/streamer",
            "https://pin.it/123456",
            "https://cdn.example.com/stream.m3u8",
            "https://example.com/video.mp4?token=abc&expiry=123",
            "https://noticias.example.com/articulo/video",
            "youtube.com/watch?v=test",
            "tiktok.com/@user/video/123",
        ]
        for url in valid_urls:
            self.assertTrue(is_valid_url(url), f"Fallo al validar URL válida: {url}")
            self.assertTrue(is_valid_media_url(url), f"Fallo en alias is_valid_media_url: {url}")

    def test_is_valid_url_invalid_cases(self):
        invalid_urls = [
            "",
            None,
            "   ",
            "not a url",
            "ftp://files.example.com/file.mp4",
            "javascript:alert(1)",
            "http://",
            "https://",
            "https://com",
            "http://.com",
            "https://site with spaces.com",
            "file:///C:/path/to/video.mp4",
        ]
        for url in invalid_urls:
            self.assertFalse(is_valid_url(url), f"Validó erróneamente URL inválida: {url}")

    def test_detect_youtube(self):
        urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "https://www.youtube.com/playlist?list=PL1234567890",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.YOUTUBE)
            self.assertEqual(name, "YouTube")
            self.assertIn("YouTube", badge)

    def test_detect_tiktok(self):
        urls = [
            "https://www.tiktok.com/@user/video/1234567890",
            "https://vm.tiktok.com/ZM123456/",
            "https://m.tiktok.com/v/1234567890.html",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.TIKTOK)
            self.assertEqual(name, "TikTok")
            self.assertIn("TikTok", badge)

    def test_detect_instagram(self):
        urls = [
            "https://www.instagram.com/reel/C123456789/",
            "https://www.instagram.com/p/C123456789/",
            "https://instagr.am/tv/C123456789/",
            "https://www.instagram.com/stories/user/123456789/",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.INSTAGRAM)
            self.assertEqual(name, "Instagram")
            self.assertIn("Instagram", badge)

    def test_detect_twitter(self):
        urls = [
            "https://twitter.com/user/status/123456789",
            "https://x.com/user/status/123456789",
            "https://mobile.twitter.com/user/status/123456789",
            "https://t.co/xyz123abc",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.TWITTER)
            self.assertIn("Twitter", name)
            self.assertIn("Twitter", badge)

    def test_detect_twitch(self):
        urls = [
            "https://www.twitch.tv/videos/123456789",
            "https://clips.twitch.tv/ClipName",
            "https://www.twitch.tv/streamer_name",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.TWITCH)
            self.assertEqual(name, "Twitch")
            self.assertIn("Twitch", badge)

    def test_detect_facebook(self):
        urls = [
            "https://www.facebook.com/watch/?v=123456",
            "https://fb.watch/123456/",
            "https://fb.com/video/123456",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.FACEBOOK)
            self.assertEqual(name, "Facebook")
            self.assertIn("Facebook", badge)

    def test_detect_reddit(self):
        urls = [
            "https://www.reddit.com/r/videos/comments/123456/title/",
            "https://v.redd.it/123456789",
            "https://redd.it/123456",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.REDDIT)
            self.assertEqual(name, "Reddit")
            self.assertIn("Reddit", badge)

    def test_detect_soundcloud(self):
        urls = [
            "https://soundcloud.com/artist/track-name",
            "https://m.soundcloud.com/artist/sets/album",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.SOUNDCLOUD)
            self.assertEqual(name, "SoundCloud")
            self.assertIn("SoundCloud", badge)

    def test_detect_bandcamp(self):
        urls = [
            "https://artist.bandcamp.com/track/song-name",
            "https://bandcamp.com/album/cool-album",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.BANDCAMP)
            self.assertEqual(name, "Bandcamp")
            self.assertIn("Bandcamp", badge)

    def test_detect_vimeo(self):
        urls = [
            "https://vimeo.com/123456789",
            "https://player.vimeo.com/video/123456789",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.VIMEO)
            self.assertEqual(name, "Vimeo")
            self.assertIn("Vimeo", badge)

    def test_detect_kick(self):
        urls = [
            "https://kick.com/streamer",
            "https://kick.com/video/123456",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.KICK)
            self.assertEqual(name, "Kick")
            self.assertIn("Kick", badge)

    def test_detect_pinterest(self):
        urls = [
            "https://www.pinterest.com/pin/123456789/",
            "https://pin.it/123456",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.PINTEREST)
            self.assertEqual(name, "Pinterest")
            self.assertIn("Pinterest", badge)

    def test_detect_direct_stream(self):
        urls = [
            "https://stream.server.com/live/index.m3u8",
            "https://cdn.example.org/manifest.mpd",
            "https://media.org/video.mp4?token=123",
            "https://storage.provider.net/media/audio.mp3",
            "https://example.com/stream.webm",
            "https://example.com/music.m4a",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.DIRECT_STREAM)
            self.assertEqual(name, "Stream Directo")
            self.assertIn("Stream Directo", badge)

    def test_detect_generic_website(self):
        urls = [
            "https://noticias.example.com/noticia-con-video",
            "https://educational-site.org/course/module1",
            "https://myblog.io/awesome-embedded-player",
        ]
        for url in urls:
            ptype, name, badge = detect_platform(url)
            self.assertEqual(ptype, PlatformType.GENERIC)
            self.assertEqual(name, "Web Genérica")
            self.assertIn("Web Genérica", badge)

    def test_get_platform_info_properties(self):
        info_yt = get_platform_info("https://www.youtube.com/watch?v=123")
        self.assertTrue(info_yt.supports_playlists)
        self.assertEqual(info_yt.recommended_audio_fmt, "mp3")

        info_bc = get_platform_info("https://artist.bandcamp.com/album/test")
        self.assertTrue(info_bc.supports_playlists)
        self.assertEqual(info_bc.recommended_audio_fmt, "flac")

        info_ig = get_platform_info("https://instagram.com/reel/123")
        self.assertEqual(info_ig.recommended_audio_fmt, "m4a")

    def test_platform_folder_names_mapping(self):
        expected = {
            PlatformType.YOUTUBE: "YouTube",
            PlatformType.TIKTOK: "TikTok",
            PlatformType.INSTAGRAM: "Instagram",
            PlatformType.TWITTER: "Twitter",
            PlatformType.TWITCH: "Twitch",
            PlatformType.FACEBOOK: "Facebook",
            PlatformType.REDDIT: "Reddit",
            PlatformType.SOUNDCLOUD: "SoundCloud",
            PlatformType.BANDCAMP: "Bandcamp",
            PlatformType.VIMEO: "Vimeo",
            PlatformType.KICK: "Kick",
            PlatformType.PINTEREST: "Pinterest",
            PlatformType.DIRECT_STREAM: "Otros",
            PlatformType.GENERIC: "Otros",
        }
        for ptype, name in expected.items():
            self.assertEqual(PLATFORM_FOLDER_NAMES[ptype], name)

    def test_get_platform_folder_name(self):
        self.assertEqual(get_platform_folder_name(PlatformType.YOUTUBE), "YouTube")
        self.assertEqual(get_platform_folder_name(PlatformType.TIKTOK), "TikTok")
        self.assertEqual(get_platform_folder_name(PlatformType.INSTAGRAM), "Instagram")
        self.assertEqual(get_platform_folder_name(PlatformType.TWITTER), "Twitter")
        self.assertEqual(get_platform_folder_name(PlatformType.TWITCH), "Twitch")
        self.assertEqual(get_platform_folder_name(PlatformType.FACEBOOK), "Facebook")
        self.assertEqual(get_platform_folder_name(PlatformType.REDDIT), "Reddit")
        self.assertEqual(get_platform_folder_name(PlatformType.SOUNDCLOUD), "SoundCloud")
        self.assertEqual(get_platform_folder_name(PlatformType.BANDCAMP), "Bandcamp")
        self.assertEqual(get_platform_folder_name(PlatformType.VIMEO), "Vimeo")
        self.assertEqual(get_platform_folder_name(PlatformType.KICK), "Kick")
        self.assertEqual(get_platform_folder_name(PlatformType.PINTEREST), "Pinterest")
        self.assertEqual(get_platform_folder_name(PlatformType.DIRECT_STREAM), "Otros")
        self.assertEqual(get_platform_folder_name(PlatformType.GENERIC), "Otros")
        self.assertEqual(get_platform_folder_name(None), "Otros")


class TestUniversalClipboard(unittest.TestCase):
    @patch('pyperclip.paste')
    def test_get_clipboard_url_youtube(self, mock_paste):
        mock_paste.return_value = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        url = get_clipboard_url()
        self.assertEqual(url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @patch('pyperclip.paste')
    def test_get_clipboard_url_tiktok(self, mock_paste):
        mock_paste.return_value = "https://www.tiktok.com/@user/video/1234567890"
        url = get_clipboard_url()
        self.assertEqual(url, "https://www.tiktok.com/@user/video/1234567890")

    @patch('pyperclip.paste')
    def test_get_clipboard_url_instagram(self, mock_paste):
        mock_paste.return_value = "https://www.instagram.com/reel/C123456789/"
        url = get_clipboard_url()
        self.assertEqual(url, "https://www.instagram.com/reel/C123456789/")

    @patch('pyperclip.paste')
    def test_get_clipboard_url_direct_stream(self, mock_paste):
        mock_paste.return_value = "https://cdn.example.com/live/master.m3u8"
        url = get_clipboard_url()
        self.assertEqual(url, "https://cdn.example.com/live/master.m3u8")

    @patch('pyperclip.paste')
    def test_get_clipboard_url_without_schema(self, mock_paste):
        mock_paste.return_value = "tiktok.com/@user/video/1234567890"
        url = get_clipboard_url()
        self.assertEqual(url, "https://tiktok.com/@user/video/1234567890")

    @patch('pyperclip.paste')
    def test_get_clipboard_url_embedded_in_text(self, mock_paste):
        mock_paste.return_value = "Mira este video increíble: https://x.com/user/status/123456789 ¡no te lo pierdas!"
        url = get_clipboard_url()
        self.assertEqual(url, "https://x.com/user/status/123456789")

    @patch('pyperclip.paste')
    def test_get_clipboard_url_invalid_text(self, mock_paste):
        mock_paste.return_value = "Este es solo un texto normal sin enlaces"
        url = get_clipboard_url()
        self.assertIsNone(url)

    @patch('pyperclip.paste')
    def test_get_clipboard_url_exception_handling(self, mock_paste):
        mock_paste.side_effect = Exception("Clipboard inaccessible")
        url = get_clipboard_url()
        self.assertIsNone(url)

    @patch('utils.clipboard.Prompt.ask')
    def test_resolve_url_passed_valid_url(self, mock_ask):
        url = resolve_url("https://vimeo.com/123456789")
        self.assertEqual(url, "https://vimeo.com/123456789")
        mock_ask.assert_not_called()

    @patch('utils.clipboard.get_clipboard_url')
    @patch('utils.clipboard.Prompt.ask')
    def test_resolve_url_from_clipboard(self, mock_ask, mock_get_clip):
        mock_get_clip.return_value = "https://www.tiktok.com/@user/video/1234567890"
        mock_ask.return_value = "https://www.tiktok.com/@user/video/1234567890"

        test_console = Console(file=StringIO(), force_terminal=False)
        result = resolve_url(None, console_instance=test_console)
        self.assertEqual(result, "https://www.tiktok.com/@user/video/1234567890")
        mock_ask.assert_called_once()

    def test_is_youtube_url_backwards_compatibility(self):
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_youtube_url("https://youtu.be/dQw4w9WgXcQ"))
        self.assertFalse(is_youtube_url("https://vimeo.com/123456"))
        self.assertFalse(is_youtube_url("https://tiktok.com/@user/video/123"))
        self.assertFalse(is_youtube_url(None))


if __name__ == '__main__':
    unittest.main()
