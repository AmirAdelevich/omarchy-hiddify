"""Generate typed preference metadata from the matching upstream release.
Usage: python tools/catalog.py /path/to/hiddify-app
Only metadata is generated; upstream code is never executed.
"""
import json,re,sys,pathlib
base=pathlib.Path(sys.argv[1]); entries={}; enums={}
for p in base.joinpath('lib').rglob('*.dart'):
 text=p.read_text()
 for name,body in re.findall(r'enum\s+(\w+)\s*\{(.*?)(?:;|\})',text,re.S):
  body=re.sub(r'//[^\n]*','',body)
  pairs=re.findall(r'(\w+)\s*\(\s*[\'"]([^\'"]*)[\'"]\s*\)',body)
  plain=re.findall(r'\b(\w+)\s*(?:,|$)',body.strip())
  if pairs: enums[name]=dict(pairs)
  elif plain: enums[name]={x:x for x in plain}
files=['features/settings/data/config_option_repository.dart','core/preferences/general_preferences.dart']
for file in files:
 text=base.joinpath('lib',file).read_text()
 text=re.sub(r'^\s*//.*$', '',text,flags=re.M)
 starts=list(re.finditer(r'static final (\w+)\s*=\s*PreferencesNotifier\.create(?:<([^\n]+?)>)?\(',text))
 for index,m in enumerate(starts):
  block=text[m.end():starts[index+1].start() if index+1<len(starts) else len(text)]
  key=re.match(r'\s*[\'"]([^\'"]+)[\'"],\s*',block)
  if not key: continue
  k=key[1]; d=block[key.end():]; generics=(m[2] or '').split(','); typ=generics[-1].strip().replace('?','')
  if typ not in ('bool','int','String'): continue
  default=None; opts=[]
  literal=re.match(r'(true|false|-?\d+|"[^"\n]*"|\'[^\'\n]*\')\s*[,)]',d)
  enum=re.match(r'(\w+)\.(\w+)\s*[,)]',d)
  if literal:
   val=literal[1]
   default={'true':True,'false':False}.get(val)
   if val not in ('true','false'):
    default=val[1:-1] if val[0] in "\"'" else int(val)
  elif enum and enum[1] in enums:
   values=enums[enum[1]]
   usekeys='value.key' in block.split(');')[0] or enum[1]=='IPv6Mode'
   opts=list(values.values()) if usekeys else list(values)
   default=values.get(enum[2],enum[2]) if usekeys else enum[2]
  elif 'Duration(minutes:' in d:
   default=int(re.search(r'Duration\(minutes:\s*(\d+)',d)[1])*60
  elif 'OptionalRange(' in d:
   r=re.search(r'OptionalRange\(min:\s*(\d+),\s*max:\s*(\d+)\)',d)
   if r: default=r[1]+'-'+r[2]
  if k=='service-mode': opts=['proxy','system-proxy','vpn','router'];default='vpn'
  if k=='disable_memory_limit': default=True
  if default is None and typ=='bool': default=False
  if default is None and typ=='int': default=0
  if default is None and typ=='String': default=''
  if k in ['intro_completed','started_by_user','store_reviewed_by_user','window_position','window_size','window_maximized','last_seen_crash_report','profiles_sort','auto_apps_selection_region','auto_apps_selection_last_update','auto_apps_selection_off_by_user','warp-consent-given','psiphon-consent-given','log-filter-category']: continue
  label=re.sub(r'(?<!^)(?=[A-Z])',' ',m[1]).capitalize()
  if file.startswith('core'): group='general'
  elif any(x in k for x in ['warp','psiphon','unblocker','extra-security','chain']): group='chain'
  elif any(x in k for x in ['tls','fragment','mux']): group='tls'
  elif 'dns' in k: group='dns'
  elif any(x in k for x in ['port','tun','mtu','route','lan','proxy-auth']): group='inbound'
  else: group='routing'
  entries[k]={'key':k,'name':m[1],'label':label,'type':{'bool':'boolean','int':'integer','String':'string'}[typ],'default':default,'options':opts,'group':group,'secret':any(x in k for x in ['password','license','pairing'])}
# User-facing preferences implemented outside PreferencesNotifier.
for k,default,opts in [('theme_mode','system',['system','light','dark','black']),('locale','en',[]),('enable_analytics',False,[])]:
 entries[k]={'key':k,'name':k,'label':k.replace('_',' ').capitalize(),'type':'boolean' if isinstance(default,bool) else 'string','default':default,'options':opts,'group':'general','secret':False}
# Labels are independently maintained by localize_catalog.py.
output={'hiddifyVersion':'5.5.5','sourceCommit':'v5.5.5','entries':list(entries.values())}
pathlib.Path(__file__).resolve().parents[1].joinpath('catalog.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print('Generated',len(entries),'typed settings')
