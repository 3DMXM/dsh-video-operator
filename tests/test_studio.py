import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from common import Failure
from studio import video_settings


class VideoSettingsTests(unittest.TestCase):
    def test_default_is_full_hd_at_60fps(self):
        self.assertEqual(video_settings({}, {}), ('bilibili', '1080p', 1920, 1080, 60))

    def test_portrait_default_is_full_hd(self):
        self.assertEqual(video_settings({'platform': 'douyin'}, {})[2:], (1080, 1920, 60))

    def test_2k_preserves_platform_orientation(self):
        self.assertEqual(video_settings({'resolution': '2K'}, {})[1:], ('2k', 2560, 1440, 60))
        self.assertEqual(video_settings({'platform': 'douyin', 'resolution': '2k'}, {})[2:], (1440, 2560, 60))

    def test_project_preferences_and_request_override(self):
        project = {'platform': 'douyin', 'resolution': '2k', 'fps': 60}
        self.assertEqual(video_settings({}, project)[2:], (1440, 2560, 60))
        self.assertEqual(video_settings({'platform': 'bilibili', 'resolution': '1080P'}, project)[2:], (1920, 1080, 60))

    def test_unsupported_resolution_is_rejected(self):
        for value in ('720p', '4k', None):
            with self.subTest(value=value), self.assertRaises(Failure) as error:
                video_settings({'resolution': value}, {})
            self.assertEqual(error.exception.code, 'INVALID_RESOLUTION')

    def test_non_60fps_is_rejected(self):
        for value in (25, 30, 120, True, '60'):
            with self.subTest(value=value), self.assertRaises(Failure) as error:
                video_settings({'fps': value}, {})
            self.assertEqual(error.exception.code, 'INVALID_FPS')

    def test_invalid_platform_is_rejected(self):
        with self.assertRaises(Failure) as error:
            video_settings({'platform': 'unknown'}, {})
        self.assertEqual(error.exception.code, 'INVALID_PLATFORM')


if __name__ == '__main__':
    unittest.main()
