"""Local GPT-SoVITS narration and FFmpeg video studio."""
import json
import os
from pathlib import Path
import shutil
import sys
import wave
from common import Failure, cli, load, lock, run, save

SKILL = Path.home() / '.codex' / 'skills' / 'gpt-sovits'

def probe(path):
    data = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path]))
    return float(data['format']['duration'])

def stamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

def voice(req):
    skill = Path(req.get('skill_dir', SKILL)).expanduser().resolve()
    manifest = Path(req['dialogue']).expanduser().resolve()
    output = Path(req['output']).expanduser().resolve()
    # One global lock per local skill, including calls from different plugin projects.
    lock_path = Path.home() / '.cache/dsh-video-operator/gpt-sovits.lock'
    cmd = [sys.executable, skill/'scripts/synthesize.py', '--input', manifest, '--output', output]
    if req.get('dry_run', False):
        cmd += ['--dry-run']
    with lock(lock_path):
        result = run(cmd)
    if not req.get('dry_run', False):
        with wave.open(str(output)) as w:
            duration = w.getnframes()/w.getframerate()
        return {'audio': str(output), 'duration': duration, 'engine': 'GPT-SoVITS', 'listened': False}
    return {'dry_run': True, 'validation': result[-6000:]}

def render(req):
    from PIL import Image, ImageDraw, ImageFont
    project = load(req['project'])
    base = Path(req['project']).expanduser().resolve().parent
    scenes = project['scenes']
    if not 1 <= len(scenes) <= 100:
        raise Failure('INVALID_PROJECT', '需要1到100个分镜')
    platform = req.get('platform', project.get('platform', 'bilibili'))
    if platform not in ('bilibili', 'douyin'):
        raise Failure('INVALID_PLATFORM', platform)
    width, height = (1280, 720) if platform == 'bilibili' else (720, 1280)
    out = Path(req['output_dir']).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=False)
    font_path = project.get('font') or next((str(p) for p in [Path('/System/Library/Fonts/PingFang.ttc'), Path('/System/Library/Fonts/Supplemental/Songti.ttc'), Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists()), None)
    if not font_path:
        raise Failure('FONT_MISSING', '请在项目font字段指定支持中文的字体')
    font = ImageFont.truetype(font_path, 44 if platform == 'bilibili' else 38)
    title_font = ImageFont.truetype(font_path, 60)
    dialogue = project.get('characters')
    if dialogue:
        chars = json.loads(json.dumps(dialogue))
        for char in chars.values():
            for field in ('gpt_weights', 'sovits_weights', 'ref_audio_path'):
                if field in char:
                    char[field] = str((base / char[field]).resolve())
        save(out/'dialogue.json', {'characters': chars, 'turns': [{'speaker': s.get('speaker', next(iter(chars))), 'text': s['text'], 'pause_ms': 0} for s in scenes]})
        voice({'dialogue': str(out/'dialogue.json'), 'output': str(out/'narration.wav'), 'skill_dir': req.get('skill_dir', str(SKILL))})
        segments = load(out/'narration.segments/manifest.json')
        # Audio files are ordered by synthesize.py turn index; normalized files exclude source recordings.
        audios = sorted(p for p in (out/'narration.segments').glob('*.wav') if '.source.' not in p.name)
        if len(audios) != len(scenes):
            raise Failure('SEGMENT_MISMATCH', '配音分段数与分镜数不一致')
        engine = 'GPT-SoVITS'
    else:
        audios = [(base / s['audio']).resolve() for s in scenes]
        engine = 'provided_audio'
    clips, subtitles, elapsed = [], [], 0.0
    for i, (scene, audio) in enumerate(zip(scenes, audios), 1):
        duration = probe(audio)
        if duration <= 0:
            raise Failure('INVALID_AUDIO', str(audio))
        image = Image.new('RGB', (width, height), '#132034')
        if scene.get('image'):
            from PIL import ImageOps
            image = ImageOps.fit(Image.open(base / scene['image']).convert('RGB'), (width, height))
            overlay = Image.new('RGB', image.size, '#101827')
            image = Image.blend(image, overlay, .40)
        draw = ImageDraw.Draw(image)
        def wrap(text, font, max_width):
            lines, line = [], ''
            for ch in str(text):
                if ch == '\n' or draw.textlength(line+ch, font=font) > max_width:
                    lines.append(line); line = '' if ch == '\n' else ch
                else:
                    line += ch
            if line: lines.append(line)
            return '\n'.join(lines)
        draw.text((60, 70), wrap(scene.get('heading', project.get('title', '')), title_font, width-120), font=title_font, fill='#7dd3fc', spacing=18)
        body = wrap(scene.get('caption', scene['text']), font, width-120)
        bbox = draw.multiline_textbbox((0,0), body, font=font, spacing=18)
        if bbox[3] > height * .65:
            raise Failure('TEXT_OVERFLOW', f'分镜{i}文字过长，请拆分')
        draw.multiline_text((60, max(height*.38, 220)), body, font=font, fill='white', spacing=18)
        frame, clip = out/f'frame-{i:03}.png', out/f'clip-{i:03}.mp4'
        image.save(frame)
        if i == 1: image.save(out/'cover.png')
        run(['ffmpeg', '-v', 'error', '-n', '-loop', '1', '-i', frame, '-i', audio, '-t', str(duration), '-r', '25', '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-shortest', clip])
        clips.append(clip)
        subtitles.append(f'{i}\n{stamp(elapsed)} --> {stamp(elapsed+duration)}\n{scene["text"]}\n')
        elapsed += duration
    concat = out/'clips.txt'
    concat.write_text('\n'.join(f"file '{p.name}'" for p in clips), encoding='utf-8')
    run(['ffmpeg', '-v', 'error', '-n', '-f', 'concat', '-safe', '1', '-i', concat, '-c', 'copy', '-movflags', '+faststart', out/'video.mp4'])
    (out/'subtitles.srt').write_text('\n'.join(subtitles), encoding='utf-8')
    result = {'video': str(out/'video.mp4'), 'cover': str(out/'cover.png'), 'subtitles': str(out/'subtitles.srt'), 'duration': probe(out/'video.mp4'), 'platform': platform, 'width': width, 'height': height, 'voice_engine': engine, 'listened': False}
    save(out/'manifest.json', result)
    return result

def dispatch(req):
    if req['action'] == 'doctor':
        try:
            import PIL
            pillow = PIL.__version__
        except ImportError: pillow = None
        return {'python': sys.executable, 'ffmpeg': shutil.which('ffmpeg'), 'ffprobe': shutil.which('ffprobe'), 'pillow': pillow, 'sovits_skill': str(SKILL), 'sovits_script_exists': (SKILL/'scripts/synthesize.py').is_file()}
    if req['action'] == 'voice': return voice(req)
    if req['action'] == 'render': return render(req)
    raise Failure('INVALID_ACTION', req['action'])

if __name__ == '__main__': cli(dispatch)
