"""Complete the release's bilingual UI labels without changing preference keys."""
import json,pathlib,re
root=pathlib.Path(__file__).resolve().parents[1]
d=json.loads((root/'catalog.json').read_text())
labels={
'reduce_animations':('Reduce animations','Уменьшить анимации'),
'show_sleeping_proxies':('Show sleeping proxies','Показывать спящие серверы'),
'log-level':('Log level','Уровень журналирования'),
'ipv6-mode':('IPv6 mode','Режим IPv6'),
'enable-mixed-port':('Enable local proxy port','Включить порт локального прокси'),
'enable-tproxy-port':('Enable transparent proxy port','Включить порт прозрачного прокси'),
'enable-redirect-port':('Enable redirect port','Включить порт перенаправления'),
'enable-direct-port':('Enable direct port','Включить порт прямого подключения'),
'enable-clash-api':('Enable Clash API','Включить Clash API'),
'allow-connection-from-lan':('Allow LAN connections','Разрешить подключения из локальной сети'),
'lan_sharing_password':('LAN sharing password','Пароль общего доступа в локальной сети'),
'hide-local-proxy-on-pick':('Hide local proxy instructions','Скрывать подсказки локального прокси'),
'independent-dns-cache':('Independent DNS cache','Независимый кеш DNS'),
'enable-mux':('Enable multiplexing','Включить мультиплексирование'),
'mux-padding':('Multiplexing padding','Дополнение пакетов мультиплексирования'),
'mux-max-streams':('Maximum multiplexed streams','Максимальное число потоков'),
'mux-protocol':('Multiplexing protocol','Протокол мультиплексирования'),
'disable_memory_limit':('Disable memory limit','Отключить ограничение памяти'),
'per_app_proxy_enabled':('Enable per-app routing','Включить маршрутизацию по приложениям'),
'per_app_proxy_mode':('Per-app routing mode','Режим маршрутизации приложений'),
'mark_new_profile_active':('Activate newly imported profiles','Активировать новые профили'),
'auto_check_ip':('Check IP address automatically','Автоматически проверять IP-адрес'),
'action_at_close':('When closing the window','При закрытии окна'),
'log-buffer-size':('Log buffer size','Размер буфера журнала'),
'log-filter-level':('Log filter level','Уровень фильтрации журнала'),
'fragment-packets':('Packets to fragment','Пакеты для фрагментации'),
'chain-status':('Connection chain','Цепочка подключения'),
'extra-security-mode':('Extra security method','Способ дополнительной защиты'),
'unblocker-mode':('Unblocking method','Способ обхода блокировок'),
'extra-security-profile-id':('Extra security profile ID','ID профиля дополнительной защиты'),
'unblocker-profile-id':('Unblocking profile ID','ID профиля обхода блокировок'),
'extra-security-psiphon-region':('Extra security: Psiphon region','Дополнительная защита: регион Psiphon'),
'unblocker-psiphon-region':('Unblocking: Psiphon region','Обход блокировок: регион Psiphon'),
'extra-security-psiphon-conduit-pairing-id':('Extra security: Psiphon pairing ID','Дополнительная защита: ID сопряжения Psiphon'),
'unblocker-psiphon-conduit-pairing-id':('Unblocking: Psiphon pairing ID','Обход блокировок: ID сопряжения Psiphon'),
'upload-test-limit':('Maximum servers in a speed test','Число серверов для теста скорости'),
'speed-test-direction':('Speed test direction','Направление теста скорости'),
'url-test-interval':('Latency test interval (seconds)','Интервал проверки задержки (секунды)'),
'upload-test-size':('Upload test size (MB)','Объём теста отправки (МБ)'),
'enable-fake-dns':('Enable fake DNS','Включить Fake DNS'),
'enable-tls-padding':('Enable TLS padding','Включить дополнение TLS-пакетов'),
'enable-tls-mixed-sni-case':('Use mixed-case SNI','Использовать смешанный регистр SNI'),
'extra-security-warp-license-key':('Extra security: WARP license key','Дополнительная защита: ключ лицензии WARP'),
'extra-security-warp-tunnel':('Extra security: WARP tunnel','Дополнительная защита: туннель WARP'),
'extra-security-warp-mtu':('Extra security: WARP MTU','Дополнительная защита: MTU WARP'),
'unblocker-warp-license-key':('Unblocking: WARP license key','Обход блокировок: ключ лицензии WARP'),
'unblocker-warp-tunnel':('Unblocking: WARP tunnel','Обход блокировок: туннель WARP'),
'unblocker-warp-clean-ip':('WARP endpoint IP address','IP-адрес точки подключения WARP'),
'unblocker-warp-mtu':('Unblocking: WARP MTU','Обход блокировок: MTU WARP'),
'unblocker-warp-port':('WARP endpoint port (0 = automatic)','Порт WARP (0 — автоматически)'),
'unblocker-warp-noise':('WARP noise packet count','Число шумовых пакетов WARP'),
'unblocker-warp-noise-mode':('WARP noise mode','Режим шумовых пакетов WARP'),
'unblocker-warp-noise-delay':('WARP noise delay','Задержка шумовых пакетов WARP'),
'unblocker-warp-noise-size':('WARP noise packet size','Размер шумовых пакетов WARP'),
'unblocker-warp-endpoint':('WARP endpoint source','Источник точки подключения WARP'),
'unblocker-warp-scanner':('WARP scanner settings (JSON)','Настройки сканера WARP (JSON)'),
'unblocker-warp-masque':('WARP MASQUE settings (JSON)','Настройки MASQUE для WARP (JSON)'),
'unblocker-warp-awg':('WARP AmneziaWG settings (JSON)','Настройки AmneziaWG для WARP (JSON)'),
}
options={
'proxy':('Proxy only','Только прокси'),'system-proxy':('System proxy','Системный прокси'),'vpn':('VPN (TUN)','VPN (TUN)'),
'router':('Router','Маршрутизатор'),'round-robin':('Round robin','По очереди'),'consistent-hashing':('Consistent hashing','Согласованное хеширование'),'sticky-sessions':('Sticky sessions','Закрепление сеансов'),
'lowest':('Lowest latency','Минимальная задержка'),'balance':('Load balancing','Балансировка нагрузки'),'first':('First available server','Первый доступный сервер'),
'ir':('Iran','Иран'),'cn':('China','Китай'),'ru':('Russia','Россия'),'af':('Afghanistan','Афганистан'),'id':('Indonesia','Индонезия'),'tr':('Turkey','Турция'),'br':('Brazil','Бразилия'),'other':('Other','Другой'),
'ipv4_only':('IPv4 only','Только IPv4'),'ipv6_only':('IPv6 only','Только IPv6'),'prefer_ipv4':('Prefer IPv4','Предпочитать IPv4'),'prefer_ipv6':('Prefer IPv6','Предпочитать IPv6'),'':('Automatic','Автоматически'),
'sing15':('sing-tun (default)','sing-tun (по умолчанию)'),'mixed':('Mixed','Смешанная'),'system':('System','Системная'),'gvisor':('gVisor','gVisor'),
'download':('Download','Загрузка'),'upload':('Upload','Отправка'),'both':('Download and upload','Загрузка и отправка'),
'off':('Off','Выключено'),'extraSecurity':('Extra security','Дополнительная защита'),'unblocker':('Unblocking','Обход блокировок'),
'auto':('Automatic','Автоматически'),'psiphon':('Psiphon','Psiphon'),'warp':('WARP','WARP'),'profile':('Profile','Профиль'),
'wireguard':('WireGuard','WireGuard'),'amneziaWg':('AmneziaWG','AmneziaWG'),'masque':('MASQUE','MASQUE'),
'include':('Proxy selected apps','Проксировать выбранные приложения'),'exclude':('Bypass selected apps','Пропускать выбранные приложения напрямую'),
'ask':('Ask every time','Спрашивать каждый раз'),'hide':('Minimize to tray','Свернуть в трей'),'exit':('Exit Hiddify','Завершить Hiddify'),
'light':('Light','Светлая'),'dark':('Dark','Тёмная'),'black':('Black','Чёрная'),'scan':('Scan automatically','Автоматическое сканирование'),'custom':('Custom endpoint','Указать вручную'),
'trace':('Trace','Трассировка'),'debug':('Debug','Отладка'),'info':('Information','Информация'),'warn':('Warnings','Предупреждения'),'error':('Errors','Ошибки'),'fatal':('Fatal errors','Критические ошибки'),'panic':('Panic','Аварийное завершение')}
ru_countries='Австрия Австралия Бельгия Болгария Канада Швейцария Чехия Германия Дания Эстония Испания Финляндия Франция Великобритания Хорватия Венгрия Ирландия Индия Италия Япония Латвия Нидерланды Норвегия Польша Португалия Румыния Сербия Швеция Сингапур Словакия США'.split()
countries=next(e['options'][1:] for e in d['entries'] if e['key']=='extra-security-psiphon-region')
for country,ru in zip(countries,ru_countries):options[country]=(re.sub(r'(?<!^)(?=[A-Z])',' ',country).title(),ru)
for e in d['entries']:
 if e['key'] in labels:e['label_en'],e['label_ru']=labels[e['key']]
 e.setdefault('label_en',e['label'])
 assert e.get('label_ru'),e['key']
 e['options_en']={};e['options_ru']={}
 for value in e.get('options',[]):
  pair=options.get(value,(value,value))
  if e['key']=='theme_mode' and value=='system':pair=('Follow system','Как в системе')
  if e['key']=='unblocker-warp-endpoint' and value=='profile':pair=('Assigned by Cloudflare','Назначенная Cloudflare')
  e['options_en'][value],e['options_ru'][value]=pair
(root/'catalog.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
