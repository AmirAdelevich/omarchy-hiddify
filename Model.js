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
  return kind === 'quit' ? items[5] : kind === 'connection' ? items[2] : null;
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
