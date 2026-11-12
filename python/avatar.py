"""Local Live2D frame export and audio amplitude lip sync; no microphone."""
from array import array
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from common import Failure, load, run, save

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / 'glossmod/看板娘/mod-inn-muduo/live2d'


def avatar_settings(project, req, platform, base):
    value = project.get('live2d')
    if value is None or value is False:
        return None
    if not isinstance(value, dict):
        raise Failure('INVALID_LIVE2D', 'live2d须为对象或false')
    if value.get('enabled', True) is False:
        return None
    root = Path(value.get('root') or req.get('live2d_root') or DEFAULT_ROOT).expanduser()
    if not root.is_absolute(): root = base / root
    root = root.resolve()
    release = load(root/'release.json')
    motion = value.get('motion', 'Idle')
    expression = value.get('expression', 'Neutral')
    if motion not in release['motions'] or expression not in release['expressions']:
        raise Failure('INVALID_LIVE2D_ACTION', '动作或表情未在当前Live2D版本注册')
    defaults = {'x':.68,'y':.10,'width':.30,'height':.90} if platform=='bilibili' else {'x':.50,'y':.55,'width':.48,'height':.45}
    box = {**defaults, **value.get('box',{})}
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in box.values()):
        raise Failure('INVALID_LIVE2D_BOX', '角色位置和尺寸须为有限数值')
    if not 0 < box['width'] <= 1 or not 0 < box['height'] <= 1 or box['x'] < 0 or box['y'] < 0 or box['x']+box['width']>1.000001 or box['y']+box['height']>1.000001:
        raise Failure('INVALID_LIVE2D_BOX', '角色box使用0到1的画布比例，必须完全位于画面内')
    return {**value,'root':str(root),'motion':motion,'expression':expression,'box':box,'release':release}


def rms_envelope(samples, sample_rate, fps, duration):
    count = math.ceil(duration*fps)
    levels=[]
    for index in range(count):
        section=samples[round(index*sample_rate/fps):round((index+1)*sample_rate/fps)]
        rms=math.sqrt(sum(value*value for value in section)/max(len(section),1))/32768
        levels.append(max(0.0, rms-.008))
    peak=max(levels,default=0)
    if peak <= .001: return [0.0]*count
    smoothed=[]
    previous=0.0
    for value in levels:
        target=min(.85,value/max(peak,.08))
        previous=previous*.35+target*.65
        smoothed.append(round(previous,5))
    return smoothed


def render_avatar(settings, scene, audio, duration, fps, width, height, out, index, req):
    motion=scene.get('live2d',{}).get('motion',settings['motion'])
    expression=scene.get('live2d',{}).get('expression',settings['expression'])
    release=settings['release']
    if motion not in release['motions'] or expression not in release['expressions']:
        raise Failure('INVALID_LIVE2D_ACTION', '分镜动作或表情未注册；不支持Wave、GuideLeft和GuideRight')
    node=req.get('node_path') or shutil.which('node')
    if not node: raise Failure('NODE_MISSING','Live2D视频导出需要Node.js及npm install后的playwright')
    p=subprocess.run(['ffmpeg','-v','error','-i',str(audio),'-f','s16le','-acodec','pcm_s16le','-ac','1','-ar','16000','pipe:1'],capture_output=True,timeout=300)
    if p.returncode: raise Failure('AUDIO_DECODE_FAILED','无法为Live2D口型读取配音')
    samples=array('h');samples.frombytes(p.stdout)
    if sys.byteorder!='little': samples.byteswap()
    envelope=rms_envelope(samples,16000,fps,duration)
    box=settings['box']
    avatar_width=max(2,round(width*box['width']))
    avatar_height=max(2,round(height*box['height']))
    frames=out/f'live2d-{index:03}'
    report=out/f'live2d-{index:03}.json'
    chrome = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    default_browser = str(chrome) if sys.platform == 'darwin' and chrome.is_file() else ''
    request={'root':settings['root'],'width':avatar_width,'height':avatar_height,'fps':fps,'envelope':envelope,'framesDir':str(frames),'report':str(report),'motion':motion,'expression':expression,'lipSync':settings.get('lip_sync',True),'browserExecutable':req.get('browser_executable') or settings.get('browser_executable') or default_browser}
    request_path=out/f'live2d-{index:03}-request.json'
    save(request_path,request)
    script=Path(__file__).resolve().parents[1]/'live2d/render.mjs'
    run([node,script,'--request',request_path],timeout=1800,env={**os.environ,'ELECTRON_RUN_AS_NODE':'1'})
    return {'frames':str(frames/'%06d.png'),'first_frame':str(frames/'000000.png'),'x':round(width*box['x']),'y':round(height*box['y']),'report':load(report)}
