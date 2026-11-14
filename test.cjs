const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const model = vm.createContext({});
vm.runInContext(fs.readFileSync(__dirname + '/Model.js', 'utf8'), model);
for (const value of ['<img src="https://example.invalid/tracker">', '<b>VPN</b>', '&<script>']) {
  assert(!/[<>]/.test(model.safeTooltip(value)));
}
assert(model.isHiddify('app.hiddify.com', ''));
assert(model.isHiddify('', 'Hiddify'));
assert(model.isHiddify('mj7kht4u1u', 'app.hiddify.com'));
assert(!model.isHiddify('other', 'Other VPN'));
const items=Array.from({length:6},(_,i)=>({isSeparator:i===1||i===4}));
assert.equal(model.menuAction(items,'quit'),items[5]);
assert.equal(model.menuAction(items,'connection'),items[2]);
assert.equal(model.menuAction(items.slice(1),'quit'),null);
assert.equal(model.menuAction([{isSeparator:false}],'connection'),null);
const source=fs.readFileSync(__dirname+'/BarWidget.qml','utf8');
for(const locale of ['en','ru']) {
 const catalog=JSON.parse(fs.readFileSync(`${__dirname}/i18n/${locale}.json`));
 for(const m of source.matchAll(/(?:root\.t|showMessage)\("([a-z_]+)"/g)) assert(m[1] === "group_" || m[1] in catalog,`${locale}: ${m[1]}`);
 for(const value of Object.values(catalog)) assert(!/[<>]/.test(model.safeTooltip(value)));
}
assert(source.includes('textFormat: Text.PlainText'));
assert(source.includes('tooltipText: Model.safeTooltip('));
console.log('Model, native menu contract, catalogs and tooltip checks passed');

assert(model.sameData([{key:'dns',value:'1.1.1.1'}],[{key:'dns',value:'1.1.1.1'}]));
assert(!model.sameData([{value:1}],[{value:2}]));
assert(model.sameData([],undefined));

for (const [args, expected] of [
  [['ru', 'en_US.UTF-8'], 'ru'], [['en','ru_RU.UTF-8'], 'en'],
  [['ru-RU','C'], 'ru'], [['de','ru_RU.UTF-8'], 'en'],
  [['', '', '', '', 'ru_RU.UTF-8'], 'ru'],
  [['', '', 'ru_RU.UTF-8', '', 'en_US.UTF-8'], 'ru'],
  [['', 'C.UTF-8', '', '', 'ru_RU.UTF-8'], 'en'],
  [['', '', '', 'ru:en', 'en_US.UTF-8'], 'ru'], [[''], 'en']
]) assert.equal(model.interfaceLanguage(...args), expected);
for (const [n, form] of [[1,'one'],[2,'few'],[5,'many'],[11,'many'],[21,'one'],[22,'few'],[1.5,'other']])
  assert.equal(model.pluralForm('ru',n),form);
const en=JSON.parse(fs.readFileSync(__dirname+'/i18n/en.json'));
const ru=JSON.parse(fs.readFileSync(__dirname+'/i18n/ru.json'));
assert.deepEqual(Object.keys(en).sort(),Object.keys(ru).sort());
const settings=JSON.parse(fs.readFileSync(__dirname+'/catalog.json')).entries;
for(const setting of settings) {
 assert(setting.label_en && setting.label_ru,setting.key);
 for(const option of setting.options || []) {
   assert(typeof setting.options_en[option]==='string',setting.key);
   assert(typeof setting.options_ru[option]==='string',setting.key);
 }
}
console.log('System language precedence, plural forms and all 91 bilingual settings passed');

const modeItems = Array.from({length:4}, (_,i) => ({isSeparator:false,hasChildren:false,checkState:i===2?2:0}));
assert.equal(model.serviceModeEntries(modeItems).length,4);
assert.equal(model.selectedServiceMode(modeItems),2);
assert.equal(model.serviceModeEntries(modeItems.slice(1)).length,0);
assert.equal(model.serviceModeEntries([{isSeparator:true},...modeItems.slice(1)]).length,0);
assert.equal(model.selectedServiceMode([]),-1);
const modeMenuItems = Array.from({length:6},(_,i)=>({isSeparator:i===1||i===4,hasChildren:i===3}));
assert.equal(model.menuAction(modeMenuItems,'mode'),modeMenuItems[3]);
assert.equal(model.menuAction(items,'mode'),null);

for (const key of Object.keys(en)) {
  assert(!/[А-Яа-яЁё]/.test(JSON.stringify(en[key])), key);
  if (typeof en[key] !== 'string') continue;
  assert.deepEqual(
    (JSON.stringify(en[key]).match(/%[0-9]+/g) || []).sort(),
    (JSON.stringify(ru[key]).match(/%[0-9]+/g) || []).sort(),
    key
  );
}
for (const key of ['quick_settings','mode_proxy','mode_system_proxy','mode_vpn','mode_router',
                   'stable_release','prerelease','update_available_kind','installer_current','installer_updating'])
  assert(typeof en[key] === 'string' && typeof ru[key] === 'string',key);
