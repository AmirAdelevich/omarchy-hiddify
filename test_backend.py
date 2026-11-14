import importlib.util,json,pathlib,sqlite3,tempfile,unittest,unittest.mock as mock,uuid,subprocess,os
spec=importlib.util.spec_from_file_location('backend',pathlib.Path(__file__).with_name('backend.py'))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
SQL='''CREATE TABLE profile_entries (id TEXT PRIMARY KEY,type TEXT NOT NULL,active INTEGER NOT NULL,name TEXT NOT NULL,url TEXT,last_update TEXT NOT NULL,update_interval INTEGER,upload INTEGER,download INTEGER,total INTEGER,expire TEXT,web_page_url TEXT,support_url TEXT,populated_headers TEXT,user_override TEXT,pinned INTEGER NOT NULL DEFAULT 0)'''
class BackendTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
  self.patches=[mock.patch.object(b,'DATA',self.root/'data'),mock.patch.object(b,'STATE',self.root/'state'),mock.patch.object(b,'PREFS',self.root/'data/shared_preferences.json'),mock.patch.object(b,'compatible',return_value=True),mock.patch.object(b,'running',return_value=False),mock.patch.object(b,'launch')]
  for p in self.patches:p.start()
  b.DATA.mkdir();(b.DATA/'configs').mkdir();b.save_json(b.PREFS,{'flutter.mixed-port':12334,'flutter.unrelated':'preserved'})
  with b.dbconnect(b.DATA/'db.sqlite') as c:c.execute(SQL)
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def test_url_validation(self):
  for s in ['http://example.org/sub','file:///etc/passwd','https://u:p@example.org/a','https://example.org:bad/a','https://example.org/\nsecret','https://']:
   with self.subTest(s=s),self.assertRaises(b.UserError):b.validate_url(s)
  self.assertEqual(b.validate_url('https://example.org/sub?token=private'),'https://example.org/sub?token=private')
  self.assertEqual(b.validate_url('hiddify://import/?url=https%3A%2F%2Fexample.org%2Fsub'),'https://example.org/sub')
 def test_type_port_enum_validation(self):
  for changes in [{'mixed-port':0},{'mixed-port':65536},{'mixed-port':True},{'strict-route':'true'},{'service-mode':'bogus'},{'unknown-key':1},{'tls-fragment-size':'30-10'},{'mtu':10}]:
   with self.subTest(changes=changes),self.assertRaises(b.UserError):b.validate_changes(changes)
  b.validate_changes({'service-mode':'vpn','mixed-port':12334,'strict-route':False,'tls-fragment-size':'10-30'})
 def test_save_preserves_unrelated_and_backup(self):
  result=b.main({'action':'save_settings','changes':{'mixed-port':12340},'baseline':{'mixed-port':12334}})
  data=b.read_json(b.PREFS);self.assertEqual(data['flutter.mixed-port'],12340);self.assertEqual(data['flutter.unrelated'],'preserved')
  self.assertEqual(b.read_json(b.STATE/'backups'/result['backup']/'shared_preferences.json')['flutter.mixed-port'],12334)
 def test_refuses_live_app(self):
  with mock.patch.object(b,'running',return_value=True),self.assertRaises(b.UserError):
   b.write_settings({'changes':{'mixed-port':12340},'baseline':{'mixed-port':12334}})
  self.assertEqual(b.read_json(b.PREFS)['flutter.mixed-port'],12334)
 def test_conflict_detection(self):
  with self.assertRaisesRegex(b.UserError,'settings_changed'):
   b.write_settings({'changes':{'mixed-port':12340},'baseline':{'mixed-port':1}})
 def test_reset_uses_native_default(self):
  b.write_settings({'changes':{'mixed-port':None},'baseline':{'mixed-port':12334}})
  self.assertNotIn('flutter.mixed-port',b.read_json(b.PREFS))
 def prepare(self):
  token=uuid.uuid4().hex;p=b.STATE/'staging'/token;p.mkdir(parents=True)
  b.save_json(p/'metadata.json',{'url':'https://example.org/sub?secret=x','name':'<img src="https://evil.invalid">','headers':{},'id':None})
  b.save_json(p/'config.json',{'outbounds':[{'type':'direct','tag':'fixture'}]})
  return token
 def test_import_and_restore(self):
  token=self.prepare();out=b.main({'action':'commit_import','token':token})
  ps=b.profiles();self.assertEqual(len(ps),1);self.assertEqual(ps[0]['active'],1)
  self.assertNotIn('url',ps[0]);self.assertTrue((b.DATA/'configs'/(ps[0]['id']+'.json')).exists())
  b.main({'action':'restore'})
  self.assertEqual(b.profiles(),[]);self.assertEqual(list((b.DATA/'configs').glob('*.json')),[])
 def test_invalid_staging_path(self):
  with self.assertRaises(b.UserError):b.commit_import({'token':'../../etc'})
 def test_selection_exactly_one_active(self):
  ids=[str(uuid.uuid4()),str(uuid.uuid4())]
  with b.dbconnect(b.DATA/'db.sqlite') as c:
   for pid in ids:c.execute('INSERT INTO profile_entries (id,type,active,name,last_update) VALUES (?,?,1,?,?)',(pid,'remote','fixture','2026-11-12T00:00:00Z'))
  b.main({'action':'select_profile','id':ids[1]})
  self.assertEqual(sum(p['active'] for p in b.profiles()),1)
  self.assertEqual(b.profiles()[0]['id'],ids[1])
 def test_no_url_or_secrets_in_profiles(self):
  self.prepare();b.main({'action':'commit_import','token':next((b.STATE/'staging').iterdir()).name})
  self.assertNotIn('secret=x',json.dumps(b.profiles()))
 def test_real_cli_import_prepare_commit(self):
  try:b.cli_command()
  except b.UserError:self.skipTest('Hiddify CLI is not installed')
  body=b'trojan://fixture-password@example.invalid:443#Fixture'
  with mock.patch.object(b,'download',return_value=(body,{'subscription-userinfo':'upload=1; download=2; total=0'})):
   result=b.prepare_import({'url':'https://example.org/sub?private=token','name':'Fixture'})
  b.main({'action':'commit_import','token':result['prepared']})
  profiles=b.profiles();self.assertEqual(profiles[0]['name'],'Fixture')
  self.assertEqual(profiles[0]['total'],1099511627776000)
  config=b.read_json(b.DATA/'configs'/(profiles[0]['id']+'.json'))
  self.assertEqual(config['outbounds'][0]['type'],'trojan')
 def test_server_selection_uses_allowed_members(self):
  with mock.patch.object(b,'server_groups',return_value=[{'name':'select','options':['node A']}]),mock.patch.object(b,'clash_request') as request:
   b.choose_server({'group':'select','name':'node A'})
   request.assert_called_once_with('/proxies/select',{'name':'node A'})
   with self.assertRaises(b.UserError):b.choose_server({'group':'select','name':'injected'})
 def test_local_api_redirect_is_rejected(self):
  with self.assertRaises(b.UserError):b.NoRedirect().redirect_request(None,None,302,'',{},'https://external.invalid')
 def test_installer_downloads_using_omarchy(self):
  bins=self.root/'bin';bins.mkdir();log=self.root/'install.log'
  for repository in [True,False]:
   for name,body in [('pacman','exit '+('0' if repository else '1')),('omarchy','printf "%s\\n" "$*" > "$INSTALL_LOG"')]:
    file=bins/name;file.write_text('#!/bin/sh\n'+body+'\n');file.chmod(0o755)
   env={**os.environ,'PATH':str(bins),'INSTALL_LOG':str(log)}
   subprocess.run(['/bin/bash',str(b.ROOT/'install.sh')],env=env,check=True,capture_output=True)
   self.assertEqual(log.read_text().strip(),'pkg add hiddify' if repository else 'pkg aur add hiddify')
 def test_install_script_fixed_commands(self):
  source=(b.ROOT/'install.sh').read_text()
  self.assertIn('omarchy pkg add hiddify',source);self.assertIn('omarchy pkg aur add hiddify',source)
  self.assertNotIn('curl',source)
if __name__=='__main__':unittest.main()
