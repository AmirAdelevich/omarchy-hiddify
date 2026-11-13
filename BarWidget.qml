import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Services.SystemTray
import qs.Ui as Ui
import qs.Commons as Commons
import "Model.js" as Model

Ui.Panel {
  id: root
  moduleName: "msi.hiddify"
  ipcTarget: "msi.hiddify"
  manageIpc: false
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight
  property var appData: ({installed: true, compatible: false, settings: [], profiles: []})
  property var changes: ({})
  property var settingsData: []
  property var profilesData: []
  property var serversData: []
  property bool connectionPending: false
  property var prefsBaseline: ({})
  property string section: "home"
  property string query: ""
  property string group: "all"
  property string messageKey: ""
  property bool messageError: false
  property var request: ({})
  property var queuedRequest: null
  property string workerOutput: ""
  property var deferred: null
  property bool stopping: false
  property bool stoppedByPlugin: false
  property int stopTicks: 0
  readonly property bool busy: stopping || connectionPending || (worker.running && request.action !== "inspect")
  readonly property int changeCount: Object.keys(changes).length
  readonly property color foreground: Commons.Color.popups.text
  readonly property bool russian: strings.language === "ru"
  readonly property var trayItem: {
    var items = SystemTray.items.values
    for (var i = 0; i < Math.min(items.length, 256); i++)
      if (Model.isHiddify(items[i].id, items[i].title)) return items[i]
    return null
  }
  readonly property bool connected: !!trayItem && String(trayItem.icon).indexOf("tray_icon_connected") !== -1
  readonly property var settingsRows: {
    var q = query.toLowerCase()
    return settingsData.filter(function(e) {
      return (group === "all" || group === e.group)
        && (!q || (e.key + " " + settingLabel(e)).toLowerCase().indexOf(q) !== -1)
    })
  }
  Language { id: strings }
  QsMenuOpener { id: nativeMenu; menu: root.trayItem ? root.trayItem.menu : null }

  function t(key) { return strings.t(key) }
  function settingLabel(e) { return root.russian ? (e.label_ru || e.label_en || e.label) : (e.label_en || e.label) }
  function settingOptions(e) {
    var labels = root.russian ? e.options_ru : e.options_en
    return (e.options || []).map(function(value) { return {value:value,label:(labels || {})[value] || value} })
  }
  function profileUpdated(raw) {
    var date = new Date(String(raw).replace(/\s+([+-]\d\d:\d\d)$/, "$1"))
    return isNaN(date.getTime()) ? String(raw) : date.toLocaleString(Qt.locale(strings.formatLocale), Locale.ShortFormat)
  }
  function showMessage(key, error) { messageKey = key; messageError = !!error }
  function valueFor(e) {
    if (changes[e.key] !== undefined) return changes[e.key] === null ? e.default : changes[e.key]
    return e.value
  }
  function change(e, value) { changes = Model.changedCopy(changes, e.key, value) }
  function run(payload) {
    if (worker.running) {
      if (payload.action !== "inspect") queuedRequest = payload
      return
    }
    request = payload
    worker.running = true
  }
  function refresh() { if (!busy && !worker.running) run({action: "inspect"}) }
  function hideApp() {
    run({action: "hide_window"})
  }
  function openApp(path) {
    if (!appData.installed) { updateHiddify(); return }
    if (path) Quickshell.execDetached(["hiddify", "hiddify:///" + path])
    else run({action: "show_window"})
  }
  property string hiddifyUpdate: ""
  function updateHiddify() {
    Quickshell.execDetached(["omarchy", "launch", "terminal", "bash", "-c",
      'python3 "$1"; read -r', "hiddify-update",
      Qt.resolvedUrl("update_hiddify.py").toString().replace(/^file:\/\//, "")])
  }
  Process {
    id: updateCheck
    command: ["python3", Qt.resolvedUrl("update_hiddify.py").toString().replace(/^file:\/\//, ""), "--check"]
    stdout: StdioCollector {
      onStreamFinished: root.hiddifyUpdate = /^\d+\.\d+\.\d+$/.test(text.trim()) ? text.trim() : ""
    }
  }
  Timer {
    interval: 3600000
    repeat: true
    running: true
    triggeredOnStart: true
    onTriggered: updateCheck.running = true
  }
  function toggleConnection() {
    if (!trayItem) { openApp(); showMessage("start_first", false); return }
    var entry = Model.menuAction(nativeMenu.children.values, "connection")
    if (!entry || !entry.enabled) { showMessage("menu_not_ready", true); return }
    connectionPending = true
    connectionTimeout.restart()
    entry.triggered()
  }
  function offline(payload) {
    if (busy || !appData.compatible) return
    if (!trayItem && !appData.running) { run(payload); return }
    var quit = Model.menuAction(nativeMenu.children.values, "quit")
    if (!quit || !quit.enabled) { showMessage("menu_not_ready", true); return }
    deferred = payload
    stoppedByPlugin = true
    stopping = true
    stopTicks = 0
    showMessage("restarting", false)
    quit.triggered()
    stopWait.start()
  }
  function save() {
    if (!changeCount || busy) return
    run({action: "validate_settings", changes: changes})
  }
  function importUrl(url, name) {
    if (busy) return
    run({action: "prepare_import", url: url, name: name})
  }
  function receive(result) {
    if (!result.ok) {
      showMessage(result.error || "operation_failed", true)
      if (stoppedByPlugin) {
        stoppedByPlugin = false
        Qt.callLater(function() { root.openApp() })
      }
      return
    }
    if (request.action === "inspect") {
      appData = result
      // Preserve delegates, focus, scroll position and open editors during polling.
      if (!Model.sameData(settingsData, result.settings)) settingsData = result.settings || []
      if (!Model.sameData(profilesData, result.profiles)) profilesData = result.profiles || []
      if (!Model.sameData(serversData, result.serverGroups)) serversData = result.serverGroups || []
      var b = {}
      for (var i = 0; i < result.settings.length; i++) b[result.settings[i].key] = result.settings[i].value
      // Do not replace the baseline while the user has unsaved changes.
      if (!changeCount) prefsBaseline = b
    } else if (request.action === "hide_window" || request.action === "show_window") {
      return
    } else if (request.action === "validate_settings") {
      Qt.callLater(function() { root.offline({action: "save_settings", changes: root.changes, baseline: root.prefsBaseline}) })
    } else if (result.prepared) {
      Qt.callLater(function() { root.offline({action: "commit_import", token: result.prepared}) })
    } else {
      stoppedByPlugin = false
      if (request.action === "save_settings") changes = ({})
      showMessage(result.message || "saved", false)
      refreshLater.restart()
    }
  }

  Process {
    id: worker
    command: ["python3", Qt.resolvedUrl("backend.py").toString().replace(/^file:\/\//, "")]
    stdinEnabled: true
    onStarted: { root.workerOutput = ""; write(JSON.stringify(root.request) + "\n") }
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.workerOutput = text
    }
    onExited: function(exitCode) {
      try { root.receive(JSON.parse(root.workerOutput)) }
      catch (e) { root.showMessage("operation_failed", true) }
      if (root.queuedRequest) {
        var next = root.queuedRequest; root.queuedRequest = null
        Qt.callLater(function() { root.run(next) })
      }
    }
  }
  Timer {
    id: stopWait
    interval: 400
    repeat: true
    onTriggered: {
      root.stopTicks++
      if (!root.trayItem && root.stopTicks >= 4) {
        stop(); root.stopping = false
        var payload = root.deferred; root.deferred = null
        root.run(payload)
      } else if (root.stopTicks > 50) {
        stop(); root.stopping = false; root.deferred = null
        root.showMessage("close_app_first", true)
      }
    }
  }
  onConnectedChanged: { connectionPending = false; connectionTimeout.stop() }
  Timer { id: connectionTimeout; interval: 8000; onTriggered: root.connectionPending = false }
  Timer { id: refreshLater; interval: 2000; onTriggered: root.refresh() }
  Timer { interval: 5000; repeat: true; running: root.opened && !root.busy; onTriggered: root.refresh() }
  Component.onCompleted: refresh()
  onOpenedChanged: if (opened) refresh()

  Ui.BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰌆"
    active: root.connected
    dimmed: !root.trayItem
    tooltipText: Model.safeTooltip(root.t(root.connected ? "connected" : "disconnected") + "\n" + root.t("bar_actions"))
    iconComponent: root.trayItem ? appIcon : null
    onPressed: function(mouseButton) {
      if (mouseButton === Qt.RightButton) root.hideApp()
      else root.toggle()
    }
  }
  Component {
    id: appIcon
    Image {
      width: 32; height: 32
      source: root.trayItem ? root.trayItem.icon : ""
      fillMode: Image.PreserveAspectFit
      asynchronous: true
      sourceSize.width: 32; sourceSize.height: 32
    }
  }

  Ui.KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    contentWidth: panel.fittedContentWidth(Commons.Style.space(500))
    contentHeight: panel.fittedContentHeight(Commons.Style.space(620), Commons.Style.space(700))
    padding: Commons.Style.space(18)
    focusTarget: panel.loadedContent
    content: FocusScope {
      readonly property real settingsScroll: settingList.contentY
      anchors.fill: parent
      implicitHeight: Commons.Style.space(620)
      Keys.onEscapePressed: root.close()
      ColumnLayout {
        anchors.fill: parent
        spacing: Commons.Style.space(12)
        RowLayout {
          Layout.fillWidth: true
          spacing: Commons.Style.space(12)
          ColumnLayout {
            Layout.fillWidth: true
            Plain { text: "Hiddify"; font.pixelSize: Commons.Style.font.heading; font.bold: true }
            Plain { text: root.appData.version + " · " + root.t(root.connected ? "connected" : "disconnected"); opacity: 0.7 }
          }
          ActionButton { text: root.t("open_app"); onClicked: root.openApp() }
          Item { Layout.preferredWidth: Commons.Style.space(4) }
          Ui.ToggleSwitch {
            id: connectionSwitch
            Layout.alignment: Qt.AlignVCenter
            checked: root.connected
            busy: root.busy
            interactive: !!root.trayItem
            onToggled: root.toggleConnection()
          }
        }
        RowLayout {
          Layout.fillWidth: true
          Repeater {
            model: ["home", "subscriptions", "servers", "settings"]
            ActionButton {
              required property string modelData
              text: root.t(modelData)
              selected: root.section === modelData
              Layout.fillWidth: true
              onClicked: root.section = modelData
            }
          }
        }
        Plain {
          Layout.fillWidth: true
          visible: root.busy || root.messageKey !== ""
          text: root.busy ? root.t(root.stopping ? "restarting" : "working") : root.t(root.messageKey)
          color: root.messageError ? Commons.Color.urgent : root.foreground
          wrapMode: Text.Wrap
        }
        ColumnLayout {
          visible: !root.appData.installed
          Layout.fillWidth: true
          Plain { text: root.t("not_installed"); wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
        Plain {
          visible: root.appData.installed && !root.appData.compatible
          Layout.fillWidth: true
          wrapMode: Text.Wrap
          text: root.t("unsupported_version")
        }
        ActionButton {
          visible: root.section === "home"
          Layout.fillWidth: true
          text: root.t("update_hiddify") + (root.hiddifyUpdate ? " · " + root.hiddifyUpdate : "")
          onClicked: root.updateHiddify()
        }
        QQC.ScrollView {
          Layout.fillWidth: true
          Layout.fillHeight: true
          visible: root.section === "home"
          clip: true
          contentWidth: availableWidth
          ColumnLayout {
            width: parent.width
            spacing: Commons.Style.space(12)
            Plain { text: root.t("dashboard_hint"); wrapMode: Text.Wrap; Layout.fillWidth: true }
            ActionButton {
              text: root.t("update_plugin")
              onClicked: Quickshell.execDetached(["omarchy", "launch", "terminal", "bash", "-c",
                'omarchy plugin update msi.hiddify --yes; read -r'])
            }
            Plain { text: strings.tn("profiles_count", root.profilesData.length).arg(strings.number((root.profilesData).length)) }
            Repeater {
              model: root.profilesData
              Rectangle {
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: profileColumn.implicitHeight + Commons.Style.space(20)
                radius: Commons.Style.space(6)
                color: Qt.alpha(root.foreground, modelData.active ? 0.10 : 0.035)
                ColumnLayout {
                  id: profileColumn
                  anchors { left: parent.left; right: parent.right; top: parent.top; margins: Commons.Style.space(10) }
                  Plain { text: (modelData.active ? "● " : "○ ") + modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                  Plain { text: root.t(modelData.active ? "active_profile" : "available_profile"); opacity: 0.65 }
                  ActionButton {
                    visible: !modelData.active
                    text: root.t("select_restart")
                    enabled: !root.busy && root.appData.compatible
                    onClicked: root.offline({action: "select_profile", id: modelData.id})
                  }
                }
              }
            }
            Plain { text: root.t("advanced_pages"); font.bold: true }
            Repeater {
              model: [{key:"routing_page",path:"settings/routing-options"},{key:"servers_page",path:"home/proxies"},{key:"logs_page",path:"logs"}]
              ActionButton {
                required property var modelData
                text: root.t(modelData.key)
                Layout.fillWidth: true
                onClicked: root.openApp(modelData.path)
              }
            }
            Plain { text: root.t("advanced_hint"); wrapMode: Text.Wrap; Layout.fillWidth: true; opacity: 0.65 }
          }
        }
        ColumnLayout {
          visible: root.section === "subscriptions"
          Layout.fillWidth: true
          Layout.fillHeight: true
          Ui.TextField { id: subscriptionName; Layout.fillWidth: true; placeholderText: root.t("subscription_name"); maximumLength: 128 }
          Ui.TextField {
            id: subscriptionUrl
            Layout.fillWidth: true
            placeholderText: "https://…"
            maximumLength: 8192
            password: true
            onAccepted: if (text && !root.busy) root.importUrl(text, subscriptionName.text)
          }
          Plain { text: root.t("import_hint"); wrapMode: Text.Wrap; Layout.fillWidth: true; opacity: 0.7 }
          ActionButton {
            Layout.fillWidth: true
            text: root.t("import_restart")
            enabled: subscriptionUrl.text !== "" && !root.busy && root.appData.compatible
            onClicked: root.importUrl(subscriptionUrl.text, subscriptionName.text)
          }
          QQC.ScrollView {
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
              width: parent.width
              spacing: Commons.Style.space(10)
              Repeater {
                model: root.profilesData
                ColumnLayout {
                  required property var modelData
                  Layout.fillWidth: true
                  Plain { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight; font.bold: true }
                  Plain { text: root.t("updated").arg(root.profileUpdated(modelData.last_update)); Layout.fillWidth: true; elide: Text.ElideRight; opacity: 0.6 }
                  ActionButton {
                    visible: modelData.type === "remote"
                    text: root.t("update_restart")
                    enabled: !root.busy && root.appData.compatible
                    onClicked: root.run({action: "prepare_import", id: modelData.id})
                  }
                }
              }
            }
          }
        }
        QQC.ScrollView {
          Layout.fillWidth: true; Layout.fillHeight: true
          visible: root.section === "servers"
          clip: true
          contentWidth: availableWidth
          ColumnLayout {
            width: parent.width
            spacing: Commons.Style.space(16)
            Plain { text: root.t("servers_hint"); wrapMode: Text.Wrap; Layout.fillWidth: true }
            Plain { visible: !(root.serversData).length; text: root.t("api_unavailable"); wrapMode: Text.Wrap; Layout.fillWidth: true }
            Repeater {
              model: root.serversData
              ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                Plain { text: modelData.name; wrapMode: Text.Wrap; Layout.fillWidth: true; font.bold: true }
                Ui.Dropdown {
                  Layout.fillWidth: true
                  showLabel: false
                  options: modelData.options.map(function(name) {
                    var delay = (modelData.delays || {})[name]
                    return {value:name,label:name + (delay > 0 ? " · " + strings.number(delay) + " ms" : "")}
                  })
                  value: modelData.now
                  enabled: !root.busy
                  onChanged: function(value) { root.run({action: "choose_server",group:modelData.name,name:value}) }
                }
                ActionButton {
                  text: root.t("test_servers")
                  visible: modelData.transport === "grpc"
                  enabled: !root.busy
                  Layout.fillWidth: true
                  onClicked: root.run({action: "test_servers",group:modelData.name})
                }
              }
            }
            ActionButton { text: root.t("servers_page"); Layout.fillWidth: true; onClicked: root.openApp("home/proxies") }
          }
        }
        ColumnLayout {
          visible: root.section === "settings"
          Layout.fillWidth: true
          Layout.fillHeight: true
          Ui.TextField { Layout.fillWidth: true; placeholderText: root.t("search_settings"); onTextEdited: root.query = text }
          Ui.Dropdown {
            Layout.fillWidth: true
            showLabel: false
            value: root.group
            options: ["all", "general", "inbound", "dns", "routing", "tls", "chain"].map(function(k) { return {value:k,label:root.t("group_"+k)} })
            onChanged: function(value) { root.group = value }
          }
          ListView {
            id: settingList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: Commons.Style.space(12)
            model: root.settingsRows
            cacheBuffer: 250
            QQC.ScrollBar.vertical: QQC.ScrollBar { policy: QQC.ScrollBar.AlwaysOn }
            delegate: ColumnLayout {
              id: settingRow
              required property var modelData
              width: settingList.width - Commons.Style.space(12)
              spacing: Commons.Style.space(4)
              RowLayout {
                Layout.fillWidth: true
                Plain { text: root.settingLabel(settingRow.modelData); wrapMode: Text.Wrap; Layout.fillWidth: true }
                Ui.ToggleSwitch {
                  visible: settingRow.modelData.type === "boolean"
                  Layout.alignment: Qt.AlignVCenter
                  checked: !!root.valueFor(settingRow.modelData)
                  onToggled: root.change(settingRow.modelData, !checked)
                }
                ActionButton {
                  text: root.t("reset_setting")
                  Layout.preferredWidth: Commons.Style.space(88)
                  onClicked: root.change(settingRow.modelData, null)
                }
              }
              Plain { text: settingRow.modelData.key; font.pixelSize: Commons.Style.font.caption; opacity: 0.5 }
              Ui.Dropdown {
                visible: (settingRow.modelData.options || []).length > 0
                Layout.fillWidth: true
                showLabel: false
                options: root.settingOptions(settingRow.modelData)
                value: String(root.valueFor(settingRow.modelData))
                onChanged: function(value) { root.change(settingRow.modelData, value) }
              }
              Ui.TextField {
                visible: settingRow.modelData.type !== "boolean" && (settingRow.modelData.options || []).length === 0
                Layout.fillWidth: true
                text: String(root.valueFor(settingRow.modelData))
                password: !!settingRow.modelData.secret
                maximumLength: 16384
                onTextEdited: {
                  if (settingRow.modelData.type === "integer") {
                    if (/^\d+$/.test(text)) root.change(settingRow.modelData, Number(text))
                    else { root.change(settingRow.modelData, text); root.showMessage("invalid_number", true) }
                  } else root.change(settingRow.modelData, text)
                }
              }
            }
          }
          Plain { text: root.t("save_hint"); wrapMode: Text.Wrap; Layout.fillWidth: true; opacity: 0.7 }
          RowLayout {
            Layout.fillWidth: true
            ActionButton {
              text: root.t("apply_count").arg(strings.number(root.changeCount))
              enabled: root.changeCount > 0 && !root.busy && root.appData.compatible
              Layout.fillWidth: true
              onClicked: root.save()
            }
            ActionButton { text: root.t("discard"); enabled: !root.busy && root.changeCount > 0; onClicked: root.changes = ({}) }
          }
          ActionButton {
            text: root.t("restore_restart")
            enabled: !root.busy && root.appData.hasBackup && root.appData.compatible
            Layout.fillWidth: true
            onClicked: root.offline({action: "restore"})
          }
        }
      }
    }
  }
  component ActionButton: Ui.Button {
    bordered: true
    focusable: true
    implicitHeight: Commons.Style.spacing.controlHeight
    Layout.minimumHeight: Commons.Style.spacing.controlHeight
    Layout.maximumHeight: Commons.Style.spacing.controlHeight
    Layout.alignment: Qt.AlignVCenter
  }
  component Plain: Text {
    textFormat: Text.PlainText
    color: root.foreground
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.body
  }
  Commons.ShellIpc {
    target: "msi.hiddify"
    function open(): void { root.open() }
    function close(): void { root.close() }
    function page(name: string): void {
      if (["home", "subscriptions", "servers", "settings"].indexOf(name) !== -1) { root.section = name; root.open() }
    }
    function toggle(): void { root.toggle() }
    function status(): string {
      return JSON.stringify({language:strings.language,installed:root.appData.installed,version:root.appData.version,
        compatible:root.appData.compatible,available:!!root.trayItem,connected:root.connected,
        menuReady:!!Model.menuAction(nativeMenu.children.values,"connection"),settings:(root.appData.settings || []).length,profiles:(root.profilesData).length,busy:root.busy,panelY:panel.cardOrigin.y,panelHeight:panel.contentHeight,scroll:panel.loadedContent ? panel.loadedContent.settingsScroll : 0})
    }
  }
}
