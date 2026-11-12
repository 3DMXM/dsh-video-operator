import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'python'))
import platforms
from common import Failure, load
from studio import stamp

class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name)
        self.video = self.state/'sample.mp4'
        self.video.write_bytes(b'fixture-video')
        self.video_probe = patch.object(platforms, 'probe_video', return_value={'width':1920,'height':1080})
        self.mock_probe = self.video_probe.start()
        self.addCleanup(self.video_probe.stop)
        self.req = dict(action='preview', platform='bilibili', operation='publish', state_dir=str(self.state), video=str(self.video), title='测试', tags=['知识'])
    def test_preview_never_calls_platform(self):
        with patch.object(platforms, 'perform', side_effect=AssertionError('network')):
            result = platforms.dispatch(self.req)
        self.assertFalse(result['external_write'])
        self.assertTrue(result['plan']['ai_generated'])
        self.assertEqual(len(result['plan_id']), 64)
    def test_modified_file_refused(self):
        p = platforms.dispatch(self.req)
        self.video.write_bytes(b'changed')
        with self.assertRaisesRegex(Failure, '文件已变化'):
            platforms.dispatch(dict(action='execute', plan_id=p['plan_id'], state_dir=str(self.state)))
    def test_ambiguous_failure_cannot_repost(self):
        p = platforms.dispatch(self.req)
        req = dict(action='execute', plan_id=p['plan_id'], state_dir=str(self.state))
        with patch.object(platforms, 'perform', side_effect=Failure('NETWORK','uncertain')):
            with self.assertRaises(Failure): platforms.dispatch(req)
        with self.assertRaisesRegex(Failure, '已经执行'):
            platforms.dispatch(req)
    def test_success_executes_once(self):
        p = platforms.dispatch(self.req)
        req = dict(action='execute', plan_id=p['plan_id'], state_dir=str(self.state))
        with patch.object(platforms, 'perform', return_value={'bvid':'BV-test'}) as perform:
            result = platforms.dispatch(req)
            self.assertEqual(result['result']['bvid'], 'BV-test')
            self.assertEqual(perform.call_count, 1)
        with self.assertRaises(Failure): platforms.dispatch(req)
    def test_repreview_preserves_completed_status(self):
        p = platforms.dispatch(self.req)
        with patch.object(platforms,'perform',return_value={}):
            platforms.dispatch(dict(action='execute', plan_id=p['plan_id'],state_dir=str(self.state)))
        platforms.dispatch(self.req)
        self.assertEqual(load(self.state/'plans'/f'{p["plan_id"]}.json')['status'],'completed')
    def test_plan_path_traversal(self):
        with self.assertRaises(Failure):
            platforms.dispatch(dict(action='execute',plan_id='../credential',state_dir=str(self.state)))
    def test_douyin_declaration_and_limit(self):
        self.mock_probe.return_value = {'width':1080,'height':1920}
        req = dict(self.req, platform='douyin', tags=['知识'])
        self.assertIn('#AI生成', platforms.dispatch(req)['plan']['text'])
        with self.assertRaises(Failure): platforms.dispatch(dict(req, title='字'*55))
    def test_douyin_api_failure_is_not_success(self):
        response = io.BytesIO(json.dumps({'data':{'error_code':2190008}}).encode())
        with patch('urllib.request.urlopen',return_value=response):
            with self.assertRaisesRegex(Failure,'2190008'):
                platforms.request_api({'open_id':'id','access_token':'secret'},'GET','/video/list/')
    def test_douyin_string_zero_is_success(self):
        response = io.BytesIO(b'{"data":{"error_code":"0","nickname":"test"}}')
        with patch('urllib.request.urlopen',return_value=response):
            data = platforms.request_api({'open_id':'id','access_token':'secret'},'POST','/oauth/userinfo/',body={})
        self.assertEqual(data['nickname'], 'test')
    def test_expired_plan_can_be_previewed_again(self):
        first = platforms.dispatch(self.req)
        second = platforms.dispatch(self.req)
        self.assertNotEqual(first['plan_id'],second['plan_id'])
        self.assertEqual(first['plan'],second['plan'])
    def test_douyin_upload_then_create(self):
        self.mock_probe.return_value = {'width':1080,'height':1920}
        plan = platforms.normalize(dict(self.req,platform='douyin'))
        with patch.object(platforms,'request_api',side_effect=[{'video':{'video_id':'uploaded'}},{'item_id':'created'}]) as api:
            (self.state/'creds.json').write_text('{"open_id":"id","access_token":"secret"}')
            result = platforms.perform(dict(state_dir=str(self.state),douyin_credentials=str(self.state/'creds.json')),plan)
            self.assertEqual(result['item_id'],'created')
            self.assertEqual(api.call_args_list[0].args[2],'/video/upload/')
            self.assertEqual(api.call_args_list[1].kwargs['body']['video_id'],'uploaded')
    def test_bili_publish_explicit_ai_declaration(self):
        plan = platforms.normalize(self.req)
        with patch.object(platforms,'bili',return_value={}) as bili:
            platforms.perform({},plan)
        self.assertIn('--ai-declare',bili.call_args.args[1])
    def test_wrong_orientation_creates_no_plan(self):
        with self.assertRaises(Failure) as error:
            platforms.dispatch(dict(self.req,platform='douyin'))
        self.assertEqual(error.exception.code,'ORIENTATION_MISMATCH')
        self.assertFalse((self.state/'plans').exists())
    def test_execute_revalidates_legacy_plan(self):
        preview = platforms.dispatch(self.req)
        file = self.state/'plans'/f'{preview["plan_id"]}.json'
        entry = load(file)
        entry['plan'].pop('video_geometry')
        from common import save
        save(file,entry)
        self.mock_probe.return_value = {'width':1080,'height':1920}
        with patch.object(platforms,'perform') as perform:
            with self.assertRaises(Failure) as error:
                platforms.dispatch(dict(action='execute',plan_id=preview['plan_id'],state_dir=str(self.state)))
        self.assertEqual(error.exception.code,'ORIENTATION_MISMATCH')
        perform.assert_not_called()
        self.assertEqual(load(file)['status'],'preview')
    def test_srt_timing(self):
        self.assertEqual(stamp(3661.123), '01:01:01,123')

if __name__ == '__main__': unittest.main()
