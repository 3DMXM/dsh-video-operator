"""Bilibili CLI and Douyin OpenAPI adapters; preview before external writes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from common import Failure, cli, digest, load, lock, save

DOUYIN = 'https://open.douyin.com'

def required(req, key):
    value = req.get(key)
    if value is None or value == '': raise Failure('MISSING_FIELD', key)
    return value

def request_api(credentials, method, path, query=None, body=None, upload=None):
    query = dict(query or {}, open_id=required(credentials, 'open_id'))
    headers = {'access-token': required(credentials, 'access_token')}
    if upload:
        file = Path(upload)
        if file.stat().st_size > 120*1024*1024:
            raise Failure('VIDEO_TOO_LARGE', '当前适配器单次上传上限120MiB，请压缩后上传')
        boundary = 'dshVideoOperatorBoundary'
        prefix = f'--{boundary}\r\nContent-Disposition: form-data; name="video"; filename="video.mp4"\r\nContent-Type: video/mp4\r\n\r\n'.encode()
        data = prefix + file.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
        headers['Content-Type'] = 'multipart/form-data; boundary='+boundary
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        headers['Content-Type'] = 'application/json'
    else: data = None
    request = urllib.request.Request(DOUYIN+path+'?'+urllib.parse.urlencode(query), data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.load(response)
    except Exception as e:
        # Do not include request URLs or token-bearing response bodies in errors.
        raise Failure('DOUYIN_HTTP_ERROR', f'抖音请求失败：{type(e).__name__}；请检查网络和应用权限') from e
    data = result.get('data', {})
    code = data.get('error_code', result.get('error_code', 0))
    extra_code = (result.get('extra') or {}).get('error_code', 0)
    if str(code or 0) != '0' or str(extra_code or 0) != '0':
        raise Failure('DOUYIN_API_ERROR', f'抖音错误码 {code or extra_code}；请核实access_token有效期及scope授权')
    return data

def bili(req, args):
    executable = req.get('bili_executable') or shutil.which('bili')
    if not executable: raise Failure('BILI_NOT_INSTALLED', '请安装bili-agent并配置bili_executable，使用隔离的BILI_CLI_HOME扫码登录')
    env = dict(os.environ, BILI_CLI_HOME=str(Path(req['state_dir'])/'bili-cli'), PYTHONUTF8='1')
    p = subprocess.run([executable, *map(str, args)], text=True, capture_output=True, env=env, timeout=1800)
    try: result = json.loads(p.stdout)
    except ValueError: raise Failure('BILI_BAD_OUTPUT', f'bili未返回JSON（exit {p.returncode}）')
    if not result.get('ok'):
        error = result.get('error', {})
        raise Failure(str(error.get('code', 'BILI_ERROR')), str(error.get('message', 'B站请求失败')))
    if p.returncode: raise Failure('BILI_FAILED', f'bili exited {p.returncode}')
    return result.get('data')

def normalize(req):
    platform = required(req, 'platform')
    if platform not in ('bilibili', 'douyin'): raise Failure('INVALID_PLATFORM', platform)
    action = required(req, 'operation')
    if action == 'publish':
        video = Path(required(req, 'video')).expanduser().resolve()
        if not video.is_file(): raise Failure('VIDEO_MISSING', str(video))
        title = str(required(req, 'title')).strip()
        if not 1 <= len(title) <= (80 if platform == 'bilibili' else 55):
            raise Failure('INVALID_TITLE', '标题长度不符合平台限制')
        plan = {'platform': platform, 'operation': action, 'video': str(video), 'video_sha256': digest(video), 'title': title,
                'description': req.get('description', ''), 'tags': req.get('tags', []), 'ai_generated': True}
        if platform == 'bilibili' and not 1 <= len(plan['tags']) <= 10:
            raise Failure('INVALID_TAGS', 'B站需1到10个标签')
        for key in ('cover', 'tid', 'zone', 'schedule'):
            if req.get(key) is not None: plan[key] = req[key]
        if plan.get('cover'):
            cover = Path(plan['cover']).expanduser().resolve()
            if not cover.is_file(): raise Failure('COVER_MISSING', str(cover))
            plan.update(cover=str(cover), cover_sha256=digest(cover))
        if platform == 'douyin':
            if req.get('schedule') or req.get('cover'):
                raise Failure('UNSUPPORTED_OPTION', '抖音当前适配器不支持定时及自定义封面，请移除对应字段')
            # Visible declaration is preserved even for applications whose API lacks a dedicated AIGC field.
            plan['text'] = title + ' ' + ' '.join('#'+str(t).lstrip('#') for t in plan['tags']) + ' #AI生成'
            if len(plan['text']) > 55: raise Failure('INVALID_TITLE', '抖音标题+话题+AI声明需不超过55字')
        return plan
    if action == 'reply':
        return {'platform': platform, 'operation': action, 'video_id': str(required(req, 'video_id')), 'comment_id': str(required(req, 'comment_id')), 'text': str(required(req, 'text')), **({'root': req['root']} if req.get('root') else {})}
    raise Failure('INVALID_WRITE', action)

def perform(req, plan):
    if plan['platform'] == 'bilibili':
        if plan['operation'] == 'reply':
            args = ['comment', 'reply', plan['video_id'], plan['comment_id'], plan['text']]
            if plan.get('root'): args += ['--root', plan['root']]
        else:
            args = ['upload', 'video', plan['video'], '--title', plan['title'], '--desc', plan['description'], '--ai-declare']
            for tag in plan['tags']: args += ['--tag', tag]
            for key in ('cover', 'tid', 'zone', 'schedule'):
                if plan.get(key) is not None: args += ['--'+key, plan[key]]
        return bili(req, args)
    credentials = load(required(req, 'douyin_credentials'))
    if plan['operation'] == 'reply':
        return request_api(credentials, 'POST', '/video/comment/reply/', body={'item_id': plan['video_id'], 'comment_id': plan['comment_id'], 'content': plan['text']})
    video_id = request_api(credentials, 'POST', '/video/upload/', upload=plan['video']).get('video', {}).get('video_id')
    if not video_id: raise Failure('UPLOAD_INVALID_RESPONSE', '上传结果缺少video.video_id')
    # Persist uploaded ID before creating; an ambiguous network failure must never trigger automatic reposting.
    save(Path(req['state_dir'])/'last-douyin-upload.json', {'video_id': video_id, 'time': time.time()})
    return request_api(credentials, 'POST', '/video/create/', body={'video_id': video_id, 'text': plan['text']})

def dispatch(req):
    state = Path(required(req, 'state_dir')).expanduser().resolve()
    state.mkdir(parents=True, exist_ok=True)
    action = required(req, 'action')
    if action == 'preview':
        plan = normalize(req)
        plan_id = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode() + os.urandom(32)).hexdigest()
        file = state/'plans'/f'{plan_id}.json'
        if not file.exists(): save(file, {'plan': plan, 'created': time.time(), 'status': 'preview'})
        return {'plan_id': plan_id, 'plan': plan, 'expires_in_seconds': 86400, 'external_write': False}
    if action == 'execute':
        plan_id = str(required(req, 'plan_id'))
        if len(plan_id) != 64 or any(c not in '0123456789abcdef' for c in plan_id): raise Failure('INVALID_PLAN', '无效计划ID')
        with lock(state/'write.lock'):
            file = state/'plans'/f'{plan_id}.json'
            entry = load(file)
            if entry['status'] != 'preview': raise Failure('ALREADY_ATTEMPTED', '此计划已经执行或结果待核实，请查询平台状态，不要自动重试')
            if time.time()-entry['created'] > 86400: raise Failure('PLAN_EXPIRED', '请重新预览')
            plan = entry['plan']
            if plan['operation'] == 'publish':
                for key in ('video', 'cover'):
                    if plan.get(key) and digest(plan[key]) != plan[key+'_sha256']: raise Failure('FILE_CHANGED', '文件已变化，请重新预览')
            entry.update(status='attempted', attempted=time.time())
            save(file, entry)
            try:
                result = perform(req, plan)
                entry.update(status='completed', result=result)
                save(file, entry)
                return {'plan_id': plan_id, 'result': result}
            finally:
                with open(state/'audit.jsonl', 'a', encoding='utf-8') as f:
                    os.chmod(state/'audit.jsonl', 0o600)
                    f.write(json.dumps({'time': time.time(), 'plan_id': plan_id, 'platform': plan['platform'], 'operation': plan['operation'], 'status': entry['status']})+'\n')
    platform = required(req, 'platform')
    if platform == 'bilibili':
        commands = {'account': ['auth', 'status'], 'videos': ['upload', 'list'], 'comments': ['comment', 'list', req.get('video_id', '')], 'stats': ['upload', 'stats', req.get('video_id', '')], 'status': ['upload', 'status', req.get('video_id', '')], 'zones': ['upload', 'zones']}
        if action not in commands: raise Failure('INVALID_ACTION', action)
        return bili(req, commands[action])
    if platform != 'douyin': raise Failure('INVALID_PLATFORM', platform)
    creds = load(required(req, 'douyin_credentials'))
    if action == 'account': return request_api(creds, 'POST', '/oauth/userinfo/', body={})
    if action == 'videos': return request_api(creds, 'GET', '/video/list/', {'cursor': req.get('cursor', 0), 'count': 20})
    if action == 'comments': return request_api(creds, 'GET', '/video/comment/list/', {'item_id': required(req, 'video_id'), 'cursor': req.get('cursor', 0), 'count': 20})
    if action in ('stats', 'status'): return request_api(creds, 'POST', '/video/data/', body={'item_ids': [required(req, 'video_id')]})
    raise Failure('INVALID_ACTION', action)

if __name__ == '__main__': cli(dispatch)
