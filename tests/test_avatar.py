from array import array
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from avatar import avatar_settings,rms_envelope
from common import Failure

class AvatarTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'release.json').write_text(json.dumps({'motions':['Idle','Think'],'expressions':['Neutral','Curious']}))
    def config(self,**values):
        return {'live2d':{'root':str(self.root),**values}}
    def test_opt_in_only(self):
        self.assertIsNone(avatar_settings({}, {},'bilibili',self.root))
        self.assertIsNone(avatar_settings({'live2d':False}, {},'bilibili',self.root))
        self.assertIsNone(avatar_settings(self.config(enabled=False), {},'bilibili',self.root))
    def test_platform_positions_and_configured_root(self):
        landscape=avatar_settings(self.config(),{},'bilibili',self.root)
        portrait=avatar_settings({'live2d':{}},{'live2d_root':str(self.root)},'douyin',self.root)
        self.assertEqual(landscape['box']['x'],.68)
        self.assertEqual(portrait['box']['y'],.55)
        self.assertEqual(portrait['root'],str(self.root.resolve()))
    def test_removed_motion_rejected(self):
        for motion in ('Wave','GuideLeft','GuideRight'):
            with self.assertRaises(Failure): avatar_settings(self.config(motion=motion),{},'bilibili',self.root)
    def test_invalid_box_rejected(self):
        for box in ({'x':.9,'width':.5},{'height':0},{'x':float('nan')},{'width':True}):
            with self.subTest(box=box),self.assertRaises(Failure):
                avatar_settings(self.config(box=box),{},'bilibili',self.root)
    def test_silence_and_speech_envelope(self):
        self.assertEqual(rms_envelope(array('h',[0]*16000),16000,60,1),[0.0]*60)
        levels=rms_envelope(array('h',[0]*8000+[8000]*8000),16000,60,1)
        self.assertEqual(len(levels),60)
        self.assertEqual(max(levels[:30]),0)
        self.assertGreater(max(levels[30:]),.5)
        self.assertLessEqual(max(levels),.85)
    def test_frame_count_covers_audio_duration(self):
        self.assertEqual(len(rms_envelope(array('h',[0]*1600),16000,60,.101)),7)

if __name__=='__main__':unittest.main()
