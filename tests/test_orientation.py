import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import platforms
from common import Failure

class OrientationTests(unittest.TestCase):
    def validate(self, stream, platform):
        with patch.object(platforms,'probe_video',return_value=stream):
            return platforms.validate_orientation('fixture.mp4',platform)

    def test_landscape_bili_and_portrait_douyin(self):
        self.assertEqual(self.validate({'width':1920,'height':1080},'bilibili')['orientation'],'landscape')
        self.assertEqual(self.validate({'width':1440,'height':2560},'douyin')['orientation'],'portrait')

    def test_wrong_orientation_and_square_are_rejected(self):
        for platform,width,height in [('bilibili',1080,1920),('douyin',1920,1080),('bilibili',1080,1080),('douyin',1080,1080)]:
            with self.subTest(platform=platform,width=width,height=height),self.assertRaises(Failure) as error:
                self.validate({'width':width,'height':height},platform)
            self.assertEqual(error.exception.code,'ORIENTATION_MISMATCH')

    def test_rotation_uses_display_direction(self):
        stream={'width':1920,'height':1080,'side_data_list':[{'rotation':-90}]}
        self.assertEqual(self.validate(stream,'douyin')['display_height'],1920)
        with self.assertRaises(Failure): self.validate(stream,'bilibili')
        stream={'width':1080,'height':1920,'tags':{'rotate':'90'}}
        self.assertEqual(self.validate(stream,'bilibili')['orientation'],'landscape')

    def test_sample_aspect_ratio_is_respected(self):
        stream={'width':720,'height':1080,'sample_aspect_ratio':'2:1'}
        self.assertEqual(self.validate(stream,'bilibili')['display_width'],1440)

    def test_unreliable_geometry_fails_closed(self):
        for stream in ({'width':0,'height':1080},{'width':1920,'height':1080,'tags':{'rotate':'45'}},{'width':1920,'height':1080,'sample_aspect_ratio':'bad'}):
            with self.subTest(stream=stream),self.assertRaises(Failure) as error:
                self.validate(stream,'bilibili')
            self.assertEqual(error.exception.code,'INVALID_VIDEO_GEOMETRY')

    def test_invalid_video_probe_is_reported(self):
        with patch.object(platforms.shutil,'which',return_value='/bin/ffprobe'),patch.object(platforms.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps({'streams':[]}))):
            with self.assertRaises(Failure) as error: platforms.probe_video('invalid.mp4')
        self.assertEqual(error.exception.code,'INVALID_VIDEO')

    def test_ffprobe_required(self):
        with patch.object(platforms.shutil,'which',return_value=None):
            with self.assertRaises(Failure) as error: platforms.probe_video('fixture.mp4')
        self.assertEqual(error.exception.code,'FFPROBE_MISSING')

if __name__=='__main__': unittest.main()
