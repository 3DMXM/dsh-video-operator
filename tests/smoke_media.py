"""Generate a real, synthetic test-tone clip; does not claim voice synthesis."""
import json
from pathlib import Path
import math
import struct
import sys
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from common import save
from studio import render
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
for platform in ('bilibili','douyin'):
    print(json.dumps(render({'project':str(project),'output_dir':str(root/platform),'platform':platform}),ensure_ascii=False))
