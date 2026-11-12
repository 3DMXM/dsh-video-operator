"""Generate a real, synthetic test-tone clip; does not claim voice synthesis."""
import json
from pathlib import Path
import math
import struct
import sys
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from common import save, run
from studio import render
from fractions import Fraction
from PIL import Image
import tempfile
output_root = Path(__file__).resolve().parents[1]/'test-output'
output_root.mkdir(exist_ok=True)
root = Path(tempfile.mkdtemp(prefix='smoke-', dir=output_root))
wavefile = root/'tone.wav'
with wave.open(str(wavefile),'wb') as f:
    f.setparams((1,2,32000,0,'NONE','not compressed'))
    f.writeframes(b''.join(struct.pack('<h',int(1000*math.sin(2*math.pi*440*i/32000))) for i in range(32000)))
project = root/'tone-project.json'
save(project, {'title':'视频创作运营 · 合成测试','scenes':[{'heading':'本地制片验证','text':'这是测试音频，仅验证视频与字幕合成。','audio':str(wavefile)}]})
for platform in ('bilibili', 'douyin'):
    for resolution, landscape in (('1080p', (1920, 1080)), ('2k', (2560, 1440))):
        expected = landscape if platform == 'bilibili' else landscape[::-1]
        result = render({'project': str(project), 'output_dir': str(root/f'{platform}-{resolution}'), 'platform': platform, 'resolution': resolution})
        info = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams', '-of', 'json', result['video']]))['streams'][0]
        assert (info['width'], info['height']) == expected, info
        assert Fraction(info['r_frame_rate']) == 60, info
        assert Fraction(info['avg_frame_rate']) == 60, info
        with Image.open(result['cover']) as cover:
            assert cover.size == expected
        assert result['fps'] == 60 and result['resolution'] == resolution
        print(json.dumps({**result, 'verified_frame_rate': info['avg_frame_rate']}, ensure_ascii=False))
