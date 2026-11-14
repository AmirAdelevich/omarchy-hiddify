// Shared shell tooltips can interpret markup. Escape every plugin string there.
function safeTooltip(value) {
  return String(value).slice(0, 2048).replace(/&/g, "&amp;")
    .replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function isHiddify(id, title) {
  return /(^|[^a-z])hiddify([^a-z]|$)/i.test(String(id).slice(0, 256))
    || /(^|[^a-z])hiddify([^a-z]|$)/i.test(String(title).slice(0, 256));
}
// The verified Linux Hiddify 5.5.5 menu contract. Fail closed if it changes.
function menuAction(items, kind) {
  if (!items || items.length !== 6 || !items[1].isSeparator || !items[4].isSeparator
      || items[0].isSeparator || items[2].isSeparator || items[5].isSeparator) return null;
  return kind === 'quit' ? items[5] : kind === 'connection' ? items[2] : kind === 'mode' && items[3].hasChildren ? items[3] : null;
}
function changedCopy(changes, key, value) {
  var result = Object.assign({}, changes); result[key] = value; return result;
}

// Snapshots are bounded JSON from our adapter. Stable data keeps QML delegates alive.
function sameData(previous, next) {
  return JSON.stringify(previous || []) === JSON.stringify(next || []);
}

function interfaceLanguage(omarchy, lcAll, lcMessages, language, lang) {
  var selected = String(omarchy || "").trim();
  if (/^[a-z]{2,3}(?:[-_][A-Za-z]{2})?$/.test(selected))
    return /^ru(?:[-_]|$)/i.test(selected) ? "ru" : "en";
  var locale = String(lcAll || lcMessages || language || lang || "en").split(":")[0];
  return /^ru(?:[-_.]|$)/i.test(locale) ? "ru" : "en";
}
function pluralForm(language, count) {
  if (language !== "ru") return count === 1 ? "one" : "other";
  if (count % 1 !== 0) return "other";
  var n = Math.abs(count), a = n % 10, b = n % 100;
  if (a === 1 && b !== 11) return "one";
  if (a >= 2 && a <= 4 && !(b >= 12 && b <= 14)) return "few";
  return "many";
}

// Linux Hiddify exposes these four modes in ServiceMode.choices enum order.
function serviceModeEntries(items) {
  if (!items || items.length !== 4) return [];
  for (var i = 0; i < items.length; i++)
    if (items[i].isSeparator || items[i].hasChildren) return [];
  return items;
}
function selectedServiceMode(items) {
  for (var i = 0; i < items.length; i++)
    if (items[i].checkState === 2) return i;
  return -1;
}

// The app's connection action reports actual connection state independently of
// its health badge. Unknown labels must never be interpreted as disconnected.
function connectionState(entry) {
  if (!entry) return "unknown";
  var text = String(entry.text || "").replace(/&/g, "").trim();
  var states = {
    "ይገናኙ": "off",
    "ያላቅቁ": "on",
    "በመገናኘት ላይ…": "starting",
    "በማላቀቅ ላይ…": "stopping",
    "ለውጦችን በመተግበር ላይ…": "reloading",
    "اتصال": "off",
    "قطع الاتصال": "on",
    "جار الاتصال…": "starting",
    "جاري قطع الاتصال…": "stopping",
    "جاري تطبيق التغييرات…": "reloading",
    "Qoşul": "off",
    "Bağlantını kəs": "on",
    "Qoşulur…": "starting",
    "Bağlantı kəsilir…": "stopping",
    "Dəyişikliklər tətbiq olunur…": "reloading",
    "Падключыцца": "off",
    "Адключыцца": "on",
    "Падключэнне…": "starting",
    "Адключэнне…": "stopping",
    "Прымяненне змен…": "reloading",
    "সংযোগ করুন": "off",
    "সংযোগ বিচ্ছিন্ন করুন": "on",
    "সংযোগ হচ্ছে…": "starting",
    "সংযোগ বিচ্ছিন্ন হচ্ছে…": "stopping",
    "পরিবর্তন প্রয়োগ করা হচ্ছে…": "reloading",
    "Verbinden": "off",
    "Trennen": "on",
    "Verbindung wird hergestellt …": "starting",
    "Verbindung wird getrennt …": "stopping",
    "Änderungen werden angewendet …": "reloading",
    "Connect": "off",
    "Disconnect": "on",
    "Connecting…": "starting",
    "Disconnecting…": "stopping",
    "Applying changes…": "reloading",
    "Conectar": "off",
    "Desconectar": "on",
    "Conectando…": "starting",
    "Desconectando…": "stopping",
    "Aplicando cambios…": "reloading",
    "قطع اتصال": "on",
    "در حال اتصال…": "starting",
    "در حال قطع اتصال…": "stopping",
    "در حال اعمال تغییرات…": "reloading",
    "Connecter": "off",
    "Déconnecter": "on",
    "Connexion en cours…": "starting",
    "Déconnexion en cours…": "stopping",
    "Application des modifications…": "reloading",
    "कनेक्ट करें": "off",
    "डिस्कनेक्ट करें": "on",
    "कनेक्ट हो रहा है…": "starting",
    "डिस्कनेक्ट हो रहा है…": "stopping",
    "बदलाव लागू हो रहे हैं…": "reloading",
    "Միանալ": "off",
    "Անջատվել": "on",
    "Միանում է…": "starting",
    "Անջատվում է…": "stopping",
    "Փոփոխությունները կիրառվում են…": "reloading",
    "Sambungkan": "off",
    "Putuskan": "on",
    "Menyambungkan…": "starting",
    "Memutuskan…": "stopping",
    "Menerapkan perubahan…": "reloading",
    "Connetti": "off",
    "Disconnetti": "on",
    "Connessione in corso…": "starting",
    "Disconnessione in corso…": "stopping",
    "Applicazione delle modifiche…": "reloading",
    "Қосылу": "off",
    "Ажырату": "on",
    "Қосылуда…": "starting",
    "Ажыратылуда…": "stopping",
    "Өзгерістер қолданылуда…": "reloading",
    "연결": "off",
    "연결 해제": "on",
    "연결 중…": "starting",
    "연결 해제 중…": "stopping",
    "변경 사항 적용 중…": "reloading",
    "Туташуу": "off",
    "Ажыратуу": "on",
    "Туташууда…": "starting",
    "Ажыратылууда…": "stopping",
    "Өзгөрүүлөр колдонулууда…": "reloading",
    "ချိတ်ဆက်ရန်": "off",
    "ချိတ်ဆက်မှုဖြတ်ရန်": "on",
    "ချိတ်ဆက်နေသည်…": "starting",
    "ချိတ်ဆက်မှု ဖြတ်နေသည်…": "stopping",
    "ပြောင်းလဲမှုများကို အသုံးချနေသည်…": "reloading",
    "Verbinding verbreken": "on",
    "Verbinden…": "starting",
    "Verbinding verbreken…": "stopping",
    "Wijzigingen toepassen…": "reloading",
    "وصل کړئ": "off",
    "قطع کړئ": "on",
    "وصلېږي…": "starting",
    "قطع کېږي…": "stopping",
    "بدلونونه پلي کېږي…": "reloading",
    "Aplicando alterações…": "reloading",
    "Подключить": "off",
    "Отключить": "on",
    "Подключение…": "starting",
    "Отключение…": "stopping",
    "Применение изменений…": "reloading",
    "Пайваст шудан": "off",
    "Қатъ кардан": "on",
    "Пайваст шуда истодааст…": "starting",
    "Қатъ шуда истодааст…": "stopping",
    "Тағйирот татбиқ мешавад…": "reloading",
    "Baglan": "off",
    "Baglanyşygy kes": "on",
    "Baglanylýar…": "starting",
    "Baglanyşyk kesilýär…": "stopping",
    "Üýtgeşmeler ulanylýar…": "reloading",
    "Bağlan": "off",
    "Bağlantıyı kes": "on",
    "Bağlanıyor…": "starting",
    "Bağlantı kesiliyor…": "stopping",
    "Değişiklikler uygulanıyor…": "reloading",
    "Підключити": "off",
    "Відключити": "on",
    "Підключення…": "starting",
    "Відключення…": "stopping",
    "Застосування змін…": "reloading",
    "کنیکٹ کریں": "off",
    "منقطع کریں": "on",
    "کنیکٹ ہو رہا ہے…": "starting",
    "منقطع ہو رہا ہے…": "stopping",
    "تبدیلیاں لاگو ہو رہی ہیں…": "reloading",
    "Ulanish": "off",
    "Ulanishni uzish": "on",
    "Ulanmoqda…": "starting",
    "Ulanish uzilmoqda…": "stopping",
    "O‘zgarishlar qo‘llanmoqda…": "reloading",
    "连接": "off",
    "断开连接": "on",
    "连接中…": "starting",
    "断开连接中…": "stopping",
    "应用更改中…": "reloading",
    "連線": "off",
    "中斷連線": "on",
    "連線中…": "starting",
    "中斷連線中…": "stopping",
    "套用變更中…": "reloading"
  };
  return states[text] || "unknown";
}
