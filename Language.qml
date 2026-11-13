import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "Model.js" as Model

QtObject {
  id: root
  property string configHome: Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config"
  readonly property string language: Model.interfaceLanguage(selection.text(),
    Quickshell.env("LC_ALL"), Quickshell.env("LC_MESSAGES"),
    Quickshell.env("LANGUAGE"), Quickshell.env("LANG"))
  readonly property string formatLocale: language === "ru" ? "ru-RU" : "en-US"
  // Omarchy owns live desktop-language changes. The environment is the fallback
  // for installations that have not selected a language in Omarchy Setup.
  property QtObject shellStrings: Commons.Translations { directory: Qt.resolvedUrl("i18n") }
  property FileView selection: FileView {
    path: root.configHome + "/omarchy/language"
    watchChanges: true; blockLoading: true; printErrors: false
    onFileChanged: reload()
  }
  property FileView russianFile: FileView {
    path: Qt.resolvedUrl("i18n/ru.json").toString().replace(/^file:\/\//, "")
    watchChanges: true; blockLoading: true; onFileChanged: reload()
  }
  property FileView englishFile: FileView {
    path: Qt.resolvedUrl("i18n/en.json").toString().replace(/^file:\/\//, "")
    watchChanges: true; blockLoading: true; onFileChanged: reload()
  }
  readonly property var russian: parse(russianFile.text())
  readonly property var english: parse(englishFile.text())
  function parse(raw) { try { return JSON.parse(raw || "{}") } catch (e) { return ({}) } }
  function value(key) {
    // Keep the shell's supported translation loader for its selected language.
    if (language === Commons.I18n.language) return shellStrings.strings[key]
    return (language === "ru" ? russian[key] : english[key]) || english[key]
  }
  function t(key) {
    var entry = value(key)
    if (entry && typeof entry === "object") entry = entry.other
    return typeof entry === "string" ? entry : key
  }
  function tn(key, count) {
    var entry = value(key)
    if (typeof entry === "string") return entry
    return entry ? (entry[Model.pluralForm(language, count)] || entry.other || key) : key
  }
  function number(value) { return Number(value).toLocaleString(Qt.locale(formatLocale), "f", 0) }
}
