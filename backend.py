#!/usr/bin/env python3
"""Hiddify 5.5.5 adapter. JSON requests arrive on stdin, never in argv/logs."""
import base64, contextlib, datetime as dt, fcntl, hashlib, json, os, pathlib, re
import shutil, sqlite3, subprocess, sys, tempfile, time, urllib.parse, urllib.request, uuid
from local_peer import AuthenticatedHTTPConnection

ROOT = pathlib.Path(__file__).resolve().parent
DATA = pathlib.Path(os.environ.get('XDG_DATA_HOME', pathlib.Path.home()/'.local/share'))/'app.hiddify.com'
STATE = pathlib.Path(os.environ.get('XDG_STATE_HOME', pathlib.Path.home()/'.local/state'))/'omarchy-hiddify'
PREFS = DATA/'shared_preferences.json'
CATALOG = json.loads((ROOT/'catalog.json').read_text())
SCHEMA = {e['key']: e for e in CATALOG['entries']}
MAX_BODY = 8*1024*1024
class UserError(Exception): pass

@contextlib.contextmanager
def dbconnect(*args, **kwargs):
    db=sqlite3.connect(*args, **kwargs)
    try:
        with db: yield db
    finally: db.close()

def read_json(path, default=None):
    if not path.exists(): return default
    if path.stat().st_size > MAX_BODY: raise UserError('file_too_large')
    return json.loads(path.read_text())

def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data); out.flush(); os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def save_json(path, data):
    atomic(path, (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode())

def private_state():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.chmod(0o700)

def executable():
    return shutil.which('hiddify') or shutil.which('hiddify', path='/usr/bin')

def installed():
    return executable() is not None

def version():
    path = executable()
    if path is None: return ''
    owner = subprocess.run(['/usr/bin/pacman', '-Qoq', path],
                           capture_output=True, text=True, timeout=5)
    if owner.returncode != 0: return ''
    package = subprocess.run(['/usr/bin/pacman', '-Q', '--', owner.stdout.strip()],
                             capture_output=True, text=True, timeout=5)
    return package.stdout.strip().split(' ', 1)[-1] if package.returncode == 0 else ''

def compatible(): return version().split('-',1)[0] == CATALOG['hiddifyVersion']

def running():
    # The GUI alone owns shared_preferences.json. Never write while it is alive.
    for proc in pathlib.Path('/proc').iterdir():
        if not proc.name.isdigit(): continue
        try:
            if proc.stat().st_uid == os.getuid() and (proc/'comm').read_text().strip() == 'hiddify': return True
        except (OSError, ProcessLookupError): pass
    return False

def require_offline():
    if running(): raise UserError('close_app_first')
    if not compatible(): raise UserError('unsupported_version')

def launch():
    path = executable()
    if path is None: raise UserError('not_installed')
    subprocess.Popen([path],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)

def window_action(show):
    subprocess.run([sys.executable, str(ROOT / 'window-hiddify.py'),
                    'restore' if show else 'minimize'], check=True, timeout=10)
    if show:
        launch()
    return {}


def snapshot():
    private_state(); folder=STATE/'backups'/(dt.datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True,mode=0o700)
    if PREFS.exists(): atomic(folder/'shared_preferences.json',PREFS.read_bytes())
    if (DATA/'db.sqlite').exists():
        with dbconnect(DATA/'db.sqlite') as source, dbconnect(folder/'db.sqlite') as dest:
            source.backup(dest)
        (folder/'db.sqlite').chmod(0o600)
    return folder

def profiles():
    if not (DATA/'db.sqlite').exists(): return []
    with dbconnect('file:'+str(DATA/'db.sqlite')+'?mode=ro',uri=True,timeout=5) as db:
        db.row_factory=sqlite3.Row
        rows=db.execute('SELECT id,type,name,active,last_update,upload,download,total,expire FROM profile_entries ORDER BY active DESC,name LIMIT 256')
        return [{k:(str(v)[:512] if isinstance(v,str) else v) for k,v in dict(row).items()} for row in rows]

def clash_request(path, payload=None):
    config=read_json(DATA/'data/current-config.json',{})
    api=config.get('experimental',{}).get('clash_api',{})
    listen=api.get('external_controller','')
    if not re.fullmatch(r'127\.0\.0\.1:[0-9]{1,5}',listen): raise UserError('api_unavailable')
    if not 1<=int(listen.rsplit(':',1)[1])<=65535: raise UserError('api_unavailable')
    secret=api.get('secret','')
    if not isinstance(secret,str) or len(secret)>8192: raise UserError('api_unavailable')
    headers={'Authorization':'Bearer '+secret,'Content-Type':'application/json'}
    try:
        port = int(listen.rsplit(':', 1)[1])
        connection = AuthenticatedHTTPConnection(port, {0, os.getuid()})
        # connect() authenticates the established peer before request() writes
        # either HTTP headers or the bearer. Redirects are never followed.
        with contextlib.closing(connection):
            connection.request('PUT' if payload is not None else 'GET', path,
                               body=json.dumps(payload) if payload is not None else None,
                               headers=headers)
            response = connection.getresponse()
            if response.status != 200 and response.status != 204:
                raise UserError('api_unavailable')
            data = response.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                raise UserError('api_unavailable')
            return json.loads(data) if data else {}
    except Exception:
        raise UserError('api_unavailable') from None

def core_request(action, **args):
    binary=ROOT/'corebridge-bin'
    if not binary.is_file(): raise UserError('api_unavailable')
    try:
        p=subprocess.run([str(binary)],input=json.dumps({'action':action,**args}),capture_output=True,text=True,timeout=5)
        if len(p.stdout)>16*1024*1024: raise UserError('api_unavailable')
        data=json.loads(p.stdout)
        if p.returncode or not data.get('ok'): raise UserError('api_unavailable')
        return data.get('result')
    except (OSError,subprocess.TimeoutExpired,ValueError): raise UserError('api_unavailable') from None

def server_groups():
    try:
        groups=core_request('groups')
        if isinstance(groups,list) and len(groups)<=32:
            for group in groups:
                group['options']=group.get('options',[])[:1000]
                group['transport']='grpc'
            return groups
    except UserError: pass
    try:
        data=clash_request('/proxies').get('proxies',{})
        if not isinstance(data,dict) or len(data)>10000: return []
        result=[]
        for name,group in data.items():
            if group.get('type')!='Selector': continue
            names=group.get('all',[])
            if not isinstance(names,list) or len(names)>10000: continue
            result.append({'name':str(name)[:512],'now':str(group.get('now',''))[:512],
                           'options':[v for v in names[:1000] if isinstance(v,str) and len(v)<=512]})
            if len(result)>=32: break
        return result
    except (UserError,ValueError,TypeError): return []

def choose_server(req):
    group=req.get('group');name=req.get('name')
    if not isinstance(group,str) or not isinstance(name,str) or len(group)>512 or len(name)>512: raise UserError('invalid_option')
    found=next((g for g in server_groups() if g['name']==group and name in g['options']),None)
    if not found: raise UserError('invalid_option')
    if found.get('transport')=='grpc': core_request('select',group=group,name=name)
    else: clash_request('/proxies/'+urllib.parse.quote(group,safe=''),{'name':name})
    return {'message':'server_selected'}

def inspect():
    prefs=read_json(PREFS,{})
    result=[]
    for entry in SCHEMA.values():
        e=dict(entry);e['value']=prefs.get('flutter.'+e['key'],e['default']);e['stored']='flutter.'+e['key'] in prefs
        result.append(e)
    return {'installed':installed(),'version':version() if installed() else '',
            'compatible':compatible() if installed() else False,'running':running(),
            'settings':result,'profiles':profiles(),'fingerprint':fingerprint(),
            'serverGroups':server_groups() if running() else [],'hasBackup': (STATE/'backups').exists() and any((STATE/'backups').iterdir())}

def fingerprint(): return hashlib.sha256(PREFS.read_bytes() if PREFS.exists() else b'').hexdigest()

def validate_changes(changes):
    if not isinstance(changes,dict) or len(changes)>len(SCHEMA): raise UserError('invalid_settings')
    for k,v in changes.items():
        e=SCHEMA.get(k)
        if not e: raise UserError('invalid_settings')
        if v is None: continue # reset removes the override, preserving the app default
        if k in ('unblocker-warp-scanner','unblocker-warp-masque','unblocker-warp-awg') and v:
            try:
                if not isinstance(json.loads(v),dict): raise ValueError()
            except (ValueError,TypeError): raise UserError('invalid_settings') from None
        typ=e['type']
        if typ=='boolean' and type(v) is not bool: raise UserError('invalid_settings')
        if typ=='integer' and (type(v) is not int or not 0<=v<=2147483647): raise UserError('invalid_number')
        if typ=='string' and (not isinstance(v,str) or len(v)>16384 or '\0' in v): raise UserError('invalid_settings')
        if e.get('options') and v not in e['options']: raise UserError('invalid_option')
        if (k.endswith('-port') or k=='mixed-port') and not (0 if k=='unblocker-warp-port' else 1)<=v<=65535: raise UserError('invalid_port')
        if k=='mtu' and not 576<=v<=65535: raise UserError('invalid_number')
        if k in ('remote-dns-address','direct-dns-address','connection-test-url') and not v.strip(): raise UserError('invalid_settings')
        if k in ('tls-fragment-size','tls-fragment-sleep','tls-padding-size','unblocker-warp-noise','unblocker-warp-noise-delay','unblocker-warp-noise-size'):
            if v and not re.fullmatch(r'\d+(?:-\d+)?',v): raise UserError('invalid_range')
            nums=[int(n) for n in v.split('-')] if v else []
            if len(nums)==2 and nums[0]>nums[1]: raise UserError('invalid_range')
    return changes

def write_settings(req):
    changes=validate_changes(req.get('changes'))
    require_offline()
    # Compare against the file after graceful exit: the app may flush on exit.
    current=read_json(PREFS,{})
    baseline=req.get('baseline',{})
    for k in changes:
        expected=baseline.get(k)
        actual=current.get('flutter.'+k,SCHEMA[k]['default'])
        if expected!=actual: raise UserError('settings_changed')
    backup=snapshot()
    for k,v in changes.items():
        if v is None: current.pop('flutter.'+k,None)
        else: current['flutter.'+k]=v
    save_json(PREFS,current)
    return {'backup':backup.name,'message':'saved'}

def validate_url(value):
    if not isinstance(value,str) or len(value)>8192 or any(ord(c)<32 for c in value): raise UserError('invalid_url')
    value=value.strip()
    if value.startswith('hiddify://import/'):
        u=urllib.parse.urlsplit(value)
        params=urllib.parse.parse_qs(u.query)
        value=params.get('url',[u.path.lstrip('/')])[0]
    try: u=urllib.parse.urlsplit(value); port=u.port
    except ValueError: raise UserError('invalid_url')
    if u.scheme!='https' or not u.hostname or u.username or u.password: raise UserError('invalid_url')
    return value

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise UserError('api_unavailable')

class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def download(url):
    req=urllib.request.Request(validate_url(url),headers={'User-Agent':'Hiddify/5.5.5 OmarchyWidget/2.0','Accept-Encoding':'identity'})
    opener=urllib.request.build_opener(HTTPSRedirect())
    try:
        with opener.open(req,timeout=20) as response:
            size=response.headers.get('Content-Length')
            if size and int(size)>MAX_BODY: raise UserError('subscription_too_large')
            body=response.read(MAX_BODY+1)
            if len(body)>MAX_BODY: raise UserError('subscription_too_large')
            if not body.strip(): raise UserError('invalid_subscription')
            headers={k.lower():v[:4096] for k,v in response.headers.items() if k.lower() in ('profile-title','subscription-userinfo','profile-update-interval','profile-web-page-url','support-url')}
            return body,headers
    except UserError: raise
    except Exception: raise UserError('download_failed') from None

def cli_command():
    path = executable()
    if path is None: raise UserError('not_installed')
    if path == '/usr/bin/hiddify' and pathlib.Path('/opt/hiddify/Hiddify.AppImage').is_file():
        return [path, 'HiddifyCli']
    for directory in (pathlib.Path(path).resolve().parent, pathlib.Path('/usr/lib/hiddify')):
        cli = directory / 'HiddifyCli'
        if cli.is_file() and os.access(cli, os.X_OK): return [str(cli)]
    raise UserError('not_installed')

def parse_subscription(body,folder):
    raw=folder/'raw';atomic(raw,body)
    out=folder/'config.json'
    try:
        p=subprocess.run([*cli_command(),'parse',str(raw),'-o',str(out)],cwd=folder,
                         stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
        if p.returncode!=0 or not out.exists(): raise UserError('invalid_subscription')
        if out.stat().st_size>MAX_BODY: raise UserError('subscription_too_large')
        parsed=read_json(out,{})
        nodes=parsed.get('outbounds',[])
        if not isinstance(nodes,list) or len(nodes)>10000 or not nodes: raise UserError('invalid_subscription')
        return out
    except subprocess.TimeoutExpired: raise UserError('parse_timeout') from None
    finally: raw.unlink(missing_ok=True)

def prepare_import(req):
    if not compatible(): raise UserError('unsupported_version')
    private_state()
    profile_id=req.get('id')
    url=req.get('url','')
    if profile_id:
        profile_id=valid_id(profile_id)
        with dbconnect(DATA/'db.sqlite') as db:
            row=db.execute('SELECT url FROM profile_entries WHERE id=?',(profile_id,)).fetchone()
            if not row or not row[0]: raise UserError('profile_not_found')
            url=row[0]
    url=validate_url(url)
    body,headers=download(url)
    token=uuid.uuid4().hex;folder=STATE/'staging'/token;folder.mkdir(parents=True,mode=0o700)
    try:
        out=parse_subscription(body,folder)
        title=req.get('name','').strip()[:128]
        if not title:
            title=headers.get('profile-title','')
            if title.startswith('base64:'):
                try: title=base64.b64decode(title[7:]).decode('utf8')
                except Exception: title=''
            title=title[:128] or urllib.parse.urlsplit(url).hostname
        save_json(folder/'metadata.json',{'url':url,'name':title,'headers':headers,'id':profile_id})
        return {'prepared':token,'message':'validated'}
    except Exception:
        shutil.rmtree(folder);raise

def valid_id(value):
    try: return str(uuid.UUID(value))
    except Exception: raise UserError('profile_not_found') from None

def commit_import(req):
    token=req.get('token','')
    if not re.fullmatch('[a-f0-9]{32}',token): raise UserError('invalid_subscription')
    folder=STATE/'staging'/token; meta=read_json(folder/'metadata.json')
    if not meta or time.time()-(folder/'metadata.json').stat().st_mtime>900: raise UserError('import_expired')
    require_offline()
    if not (DATA/'db.sqlite').exists(): raise UserError('initialize_app')
    backup=snapshot()
    with dbconnect(DATA/'db.sqlite') as db:
        existing=db.execute('SELECT id FROM profile_entries WHERE url=?',(meta['url'],)).fetchone()
        pid=meta['id'] or (existing[0] if existing else str(uuid.uuid4()))
        valid_id(pid)
        dest=DATA/'configs'/(pid+'.json')
        previous=dest.read_bytes() if dest.exists() else None
        if previous is not None: atomic(backup/(pid+'.json'),previous)
        try:
            db.execute('BEGIN IMMEDIATE')
            # A newly added subscription becomes active. Refresh retains selection.
            now=dt.datetime.now().astimezone().isoformat(sep=' ')
            headers=meta['headers'];traffic={}
            for k,v in re.findall(r'(upload|download|total|expire)=(\d+)',headers.get('subscription-userinfo','')):
                number=int(v)
                if number<=9223372036854775807: traffic[k]=number
            if traffic.get('total')==0: traffic['total']=1099511627776000
            expires=None
            if traffic.get('expire',0)>0:
                try: expires=dt.datetime.fromtimestamp(traffic['expire'],dt.timezone.utc).isoformat()
                except (ValueError,OverflowError,OSError): pass
            interval=headers.get('profile-update-interval','')
            interval=int(interval)*3600 if interval.isdigit() and 0<int(interval)<=8760 else None
            if existing or meta['id']:
                db.execute('UPDATE profile_entries SET last_update=?,upload=?,download=?,total=?,expire=?,populated_headers=? WHERE id=?',
                           (now,traffic.get('upload'),traffic.get('download'),traffic.get('total'),expires,json.dumps(headers),pid))
            else:
                db.execute('UPDATE profile_entries SET active=0')
                db.execute('INSERT INTO profile_entries (id,type,active,name,url,last_update,update_interval,upload,download,total,expire,populated_headers,pinned) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)',
                           (pid,'remote',1,meta['name'],meta['url'],now,interval,traffic.get('upload'),traffic.get('download'),traffic.get('total'),expires,json.dumps(headers)))
            atomic(dest,(folder/'config.json').read_bytes())
            db.commit()
        except Exception:
            db.rollback()
            if previous is None: dest.unlink(missing_ok=True)
            else: atomic(dest,previous)
            raise
    save_json(backup/'operation.json',{'profile':pid,'hadConfig':previous is not None})
    shutil.rmtree(folder)
    return {'message':'imported','backup':backup.name}

def select_profile(req):
    pid=valid_id(req.get('id'));require_offline()
    backup=snapshot()
    with dbconnect(DATA/'db.sqlite') as db:
        if not db.execute('SELECT 1 FROM profile_entries WHERE id=?',(pid,)).fetchone(): raise UserError('profile_not_found')
        db.execute('UPDATE profile_entries SET active=(id=?)',(pid,))
    return {'message':'profile_selected','backup':backup.name}

def restore():
    require_offline()
    folders=sorted((STATE/'backups').iterdir(),key=lambda p:p.name) if (STATE/'backups').exists() else []
    if not folders: raise UserError('no_backup')
    folder=folders[-1]
    # Snapshot current state too, so undo itself remains reversible.
    current=snapshot()
    for file in ('shared_preferences.json','db.sqlite'):
        src=folder/file
        if src.exists():
            if file=='db.sqlite':
                with dbconnect(src) as source, dbconnect(DATA/file) as dest: source.backup(dest)
            else: atomic(DATA/file,src.read_bytes())
    operation=read_json(folder/'operation.json',{})
    if operation.get('profile'):
        pid=valid_id(operation['profile']);dest=DATA/'configs'/(pid+'.json')
        if operation['hadConfig']: atomic(dest,(folder/(pid+'.json')).read_bytes())
        else: dest.unlink(missing_ok=True)
    return {'message':'restored','backup':current.name}

UPDATE_API_URL = 'https://api.github.com/repos/hiddify/hiddify-app/releases?per_page=20'
UPDATE_INTERVAL = 3600
UPDATE_RESPONSE_LIMIT = 1024 * 1024


def release_version(value):
    if not isinstance(value, str):
        raise ValueError('Invalid release version')
    match = re.fullmatch(r'v?(\d{1,6})\.(\d{1,6})\.(\d{1,6})(?:\.(\d{1,6}))?', value)
    if not match:
        raise ValueError('Invalid release version')
    return tuple(int(part or 0) for part in match.groups())


def installed_release_version(value):
    upstream = value.split(':')[-1].rsplit('-', 1)[0]
    return release_version(upstream)


def fetch_latest_release():
    request = urllib.request.Request(UPDATE_API_URL, headers={
        'User-Agent': 'Omarchy-Hiddify-Update-Checker',
        'Accept': 'application/vnd.github+json',
    })
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=12) as response:
        if response.status != 200:
            raise ValueError('Release check failed')
        raw = response.read(UPDATE_RESPONSE_LIMIT + 1)
    if len(raw) > UPDATE_RESPONSE_LIMIT:
        raise ValueError('Release response is too large')
    releases = json.loads(raw)
    if not isinstance(releases, list):
        raise ValueError('Expected a release list')
    candidates = []
    for release in releases:
        if not isinstance(release, dict) or release.get('draft') is not False:
            continue
        tag = release.get('tag_name')
        try:
            number = release_version(tag)
        except ValueError:
            continue
        url = 'https://github.com/hiddify/hiddify-app/releases/tag/' + tag
        if release.get('html_url') != url:
            continue
        candidates.append((number, {'version': tag.removeprefix('v'), 'url': url,
                                    'assets': release.get('assets', []),
                                    'prerelease': release.get('prerelease') is True}))
    if not candidates:
        raise ValueError('No versioned public release found')
    return max(candidates, key=lambda candidate: candidate[0])[1]


def load_update_state():
    try:
        state = read_json(STATE / 'updates.json', {})
    except (OSError, ValueError, UserError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    state.setdefault('enabled', True)
    state.setdefault('checkedAt', 0)
    state.setdefault('notifiedVersions', [])
    return state


def update_result(state, current):
    now = time.time()
    checked = state.get('checkedAt', 0)
    if not isinstance(checked, (int, float)) or checked < 0 or checked > now:
        checked = 0
    result = {
        'enabled': state.get('enabled') is not False,
        'installedVersion': current,
        'latestVersion': '',
        'prerelease': None,
        'releaseUrl': '',
        'checkedAt': checked,
        'status': 'updates_not_checked',
        'nextCheckSeconds': max(1, int(checked + UPDATE_INTERVAL - now)),
    }
    if not current:
        result['nextCheckSeconds'] = UPDATE_INTERVAL
        result['status'] = 'not_installed'
        return result
    if state.get('error'):
        result['status'] = 'update_check_failed'
        return result
    latest = state.get('latest')
    if isinstance(latest, dict):
        try:
            available = release_version(latest.get('version')) > installed_release_version(current)
        except (ValueError, AttributeError):
            result['status'] = 'update_version_unknown'
            return result
        result.update(
            latestVersion=latest['version'],
            prerelease=latest.get('prerelease'),
            releaseUrl=latest.get('url', ''),
            status='update_available' if available else 'updates_current',
        )
    return result


def notify_update(latest, language):
    import html
    locale = 'ru' if language == 'ru' else 'en'
    catalog = read_json(ROOT / 'i18n' / (locale + '.json'), {})
    title = catalog.get('update_notification_title', 'Hiddify update available')
    body = catalog.get('update_notification_body', 'Hiddify %1 is available. Open the widget to update.')
    body = body.replace('%1', latest['version'])
    release_kind = 'prerelease' if latest.get('prerelease') is True else 'stable_release'
    body = body.replace('%2', catalog.get(release_kind, 'Pre-release' if release_kind == 'prerelease' else 'Release'))
    try:
        process = subprocess.run(
            ['notify-send', '--app-name=Hiddify', '--icon=hiddify', '--expire-time=12000',
             '--', html.escape(title, quote=True), html.escape(body, quote=True)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=5,
        )
        return process.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def check_updates(request):
    private_state()
    # Serialize all monitors and manual/background checks, including delivery
    # bookkeeping, so the same release cannot produce duplicate notifications.
    with (STATE / 'updates.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_update_state()
        if request.get('action') == 'update_settings':
            enabled = request.get('enabled')
            if type(enabled) is not bool:
                raise UserError('invalid_settings')
            state['enabled'] = enabled
            save_json(STATE / 'updates.json', state)
            return {'updates': update_result(state, version())}
        current = version() if installed() else ''
        result = update_result(state, current)
        force = request.get('force') is True
        due = result['checkedAt'] == 0 or result['nextCheckSeconds'] <= 1
        if not current or (not force and (not result['enabled'] or not due)):
            return {'updates': result}
        try:
            state['latest'] = fetch_latest_release()
            state.pop('error', None)
        except Exception:
            state['error'] = True
        state['checkedAt'] = time.time()
        result = update_result(state, current)
        notified = state.get('notifiedVersions', [])
        if not isinstance(notified, list):
            notified = []
        latest = state.get('latest', {})
        should_notify = result['status'] == 'update_available' and latest['version'] not in notified
        if should_notify:
            # Reserve before sending. A process interruption after delivery
            # must not cause the next shell startup to show the same popup.
            state['notifiedVersions'] = notified + [latest['version']]
        save_json(STATE / 'updates.json', state)
        if should_notify and not notify_update(latest, request.get('language')):
            state['notifiedVersions'] = notified
            save_json(STATE / 'updates.json', state)
        return {'updates': result}

def main(req):
    action=req.get('action')
    if action in ('check_updates', 'update_settings'): return check_updates(req)
    if action=='inspect': return inspect()
    if action=='choose_server': return choose_server(req)
    if action=='test_servers':
        group=req.get('group')
        if not any(g['name']==group and g.get('transport')=='grpc' for g in server_groups()): raise UserError('api_unavailable')
        core_request('test',group=group)
        return {'message':'testing_servers'}
    if action in ('hide_window', 'show_window'): return window_action(action == 'show_window')
    if action=='open': launch();return {'message':'opened'}
    if action=='prepare_import': return prepare_import(req)
    if action=='validate_settings': validate_changes(req.get('changes'));return {'message':'validated'}
    if action not in ('save_settings','commit_import','select_profile','restore'): raise UserError('unknown_action')
    private_state()
    with (STATE/'write.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise UserError('busy') from None
        result={'save_settings':lambda:write_settings(req),'commit_import':lambda:commit_import(req),
                'select_profile':lambda:select_profile(req),'restore':restore}[action]()
    launch()
    return result

if __name__=='__main__':
    os.umask(0o077)
    try:
        raw=sys.stdin.buffer.readline(256*1024+1)
        if len(raw)>256*1024: raise UserError('request_too_large')
        request=json.loads(raw)
        if not isinstance(request,dict): raise UserError('invalid_request')
        result=main(request)
        print(json.dumps({'ok':True,**result},ensure_ascii=False))
    except UserError as e:
        print(json.dumps({'ok':False,'error':str(e)}))
    except Exception:
        # Credentials and subscription URLs must never appear in shell logs.
        print(json.dumps({'ok':False,'error':'operation_failed'}))
