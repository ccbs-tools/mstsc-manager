"""界面文案的中英文切换。

用法：
    from .i18n import tr, i18n
    label.setText(tr("menu.file"))
    i18n.languageChanged.connect(self.retranslate)

语言保存在 QSettings；首次运行按系统语言选择（中文系统 → zh，其他 → en）。
"""

from __future__ import annotations

from PySide6.QtCore import QLocale, QObject, QSettings, Signal

from .log import logger

LANGUAGES = (("zh", "中文（简体）"), ("en", "English"))
_SETTINGS_KEY = "language"

_STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        "app.title": "远程桌面管理器",
        # ---- 菜单 ----
        "menu.file": "文件(&F)",
        "menu.new": "新建连接(&N)",
        "menu.dup": "复制连接(&D)",
        "menu.del": "删除连接",
        "menu.import": "导入配置(&I)…",
        "menu.export": "导出配置(&E)…",
        "menu.open_dir": "打开配置目录(&O)",
        "menu.quit": "退出(&Q)",
        "menu.language": "语言(&L)",
        "menu.help": "帮助(&H)",
        "menu.open_log_dir": "打开日志目录(&L)",
        "menu.repo": "仓库主页(&R)",
        "menu.changelog": "版本介绍(&I)",
        "menu.check_update": "检查更新(&U)",
        "menu.about": "关于(&A)",
        "chg.title": "版本介绍（当前 v{ver}）",
        "chg.check": "检查版本更新",
        "chg.close": "关闭",
        "upd.title": "检查版本更新",
        "upd.checking": "正在检查更新…",
        "upd.countdown": "{sec} 秒",
        "upd.cancel": "取消",
        "upd.close": "关闭",
        "upd.download": "下载",
        "upd.latest": "已是最新版本（v{cur}）。",
        "upd.newer": "发现新版本 v{latest}（当前 v{cur}）。",
        "upd.failed_short": "检查失败，请检查网络后重试。",
        "upd.timeout": "{sec} 秒内没有响应，请检查网络后重试。",
        # ---- 工具栏 ----
        "tb.new": "新建",
        "tb.dup": "复制",
        "tb.del": "删除",
        "tb.test_port": "测试端口",
        "tb.test": "测试连接",
        "tb.connect": "连接",
        "tb.disconnect": "断开",
        # ---- 主窗口 ----
        "list.filter": "搜索名称 / 地址 / 分组",
        "panel.title": "连接状态",
        "status.config_file": "配置文件：{path}",
        "tooltip.via_ssh": "经 SSH {user}@{host}:{port}",
        "conn.new_name": "新建连接",
        "conn.copy_suffix": " - 副本",
        "conn.unnamed": "未命名",
        "del.blocked_title": "无法删除",
        "del.blocked_text": "该连接正在运行，请先断开。",
        "del.title": "删除连接",
        "del.text": "确定删除「{name}」？",
        "save.failed": "保存失败：{err}",
        "validate.title": "配置不完整",
        "validate.host": "请填写目标地址。",
        "validate.ssh_host": "已启用 SSH 隧道，请填写跳板机地址。",
        "validate.ssh_user": "已启用 SSH 隧道，请填写跳板机用户名。",
        "validate.ssh_key": "认证方式为私钥，请选择私钥文件。",
        "ssh_pwd.title": "SSH 密码",
        "ssh_pwd.text": "请输入 {user}@{host} 的密码：",
        "quit.title": "退出",
        "quit.text": "还有 {n} 个连接在运行，退出将关闭所有 SSH 隧道（远程桌面窗口会随之断线）。继续？",
        "about.title": "关于",
        "about.text": (
            "<h3>{title} v{ver}</h3>"
            "<p>管理远程桌面(mstsc)连接，支持通过 SSH 跳板机建立本地端口转发后再连接。</p>"
            "<p>配置文件：<br><code>{config}</code></p>"
            "<p>日志文件：<br><code>{log}</code></p>"
            "<p>Python {py} · PySide6 {qt} · paramiko {pm}</p>"
        ),
        "import.title": "导入配置",
        "export.title": "导出配置",
        "json.filter": "JSON 文件 (*.json);;所有文件 (*)",
        "import.done": "已导入 {n} 条连接。",
        "import.failed": "导入失败：{err}",
        "import.mode_title": "导入方式",
        "import.mode_text": "选择「合并」把导入的连接追加到现有列表（同 ID 覆盖），选择「替换」清空现有列表。",
        "import.merge": "合并",
        "import.replace": "替换",
        "export.done": "已导出 {n} 条连接到：\n{path}",
        "export.failed": "导出失败：{err}",
        # ---- 表单：远程桌面 ----
        "tab.rdp": "远程桌面",
        "tab.ssh": "SSH 隧道",
        "f.name": "名称",
        "f.group": "分组",
        "f.group_ph": "可选，用于列表分组显示",
        "f.notes": "备注",
        "f.target": "目标地址",
        "f.target_ph": "目标主机 IP / 域名",
        "f.port": "端口",
        "f.user": "用户名",
        "f.domain": "域",
        "f.optional": "可选",
        "f.resolution": "分辨率",
        "f.res_fullscreen": "全屏",
        "f.res_custom": "自定义…",
        "f.multimon": "使用所有显示器（全屏时生效）",
        "f.launch_mode": "启动方式",
        "f.launch_cli": "命令行参数（推荐，无安全确认框）",
        "f.launch_file": ".rdp 文件（设置更全，新版 Windows 每次弹确认）",
        "f.file_only_hint": "以下选项仅 .rdp 文件方式生效",
        "f.file_only_tip": "命令行方式下这些选项由 mstsc 自身的默认设置决定（文档\\Default.rdp，在 mstsc 的「选项」里改一次即长期生效）",
        "f.clipboard": "共享剪贴板",
        "f.drives": "映射本地驱动器",
        "f.smart_sizing": "窗口缩放时自动适配（智能缩放）",
        "f.ignore_cert": "不弹出服务器证书警告（走隧道时建议勾选）",
        # ---- 表单：SSH ----
        "f.ssh_group": "通过 SSH 跳板机建立本地端口转发（ssh -L）",
        "f.jump": "跳板机",
        "f.jump_ph": "跳板机 IP / 域名",
        "f.auth": "认证方式",
        "f.auth_password": "密码",
        "f.auth_key": "私钥文件",
        "f.key_ph": "例如 C:\\Users\\me\\.ssh\\id_ed25519",
        "f.browse": "浏览…",
        "f.key_label": "私钥文件",
        "f.secret_password": "密码",
        "f.secret_passphrase": "私钥口令",
        "f.secret_ph_password": "留空则连接时询问",
        "f.secret_ph_key": "私钥未加密可留空",
        "f.save_secret": "保存到本地（DPAPI 加密）",
        "f.local_listen": "本地监听",
        "f.auto": "自动",
        "f.test_port": "测试端口",
        "f.pick_port": "找空闲端口",
        "f.timeout": "连接超时",
        "f.timeout_tip": "连接跳板机、认证、打开转发通道的最长等待时间",
        "f.seconds": " 秒",
        "f.keepalive": "保活间隔",
        "f.keepalive_suffix": " 秒（0 = 关闭）",
        "f.close_with_mstsc": "远程桌面窗口关闭后自动断开隧道",
        "f.key_dialog": "选择私钥文件",
        "f.all_files": "所有文件 (*)",
        "f.port_auto_result": "自动模式，当前可用 {host}:{port}",
        # ---- 端口检查 ----
        "port.free": "{host}:{port} 空闲",
        "port.busy": "{host}:{port} 已被占用",
        "port.denied": "{host}:{port} 无权限绑定（可能被系统保留）",
        "port.error": "{host}:{port} 不可用: {err}",
        # ---- 状态面板 ----
        "step.port": "检查本地端口",
        "step.ssh": "建立 SSH 隧道",
        "step.probe": "探测目标 RDP 端口",
        "step.mstsc": "启动远程桌面",
        "st.idle": "等待",
        "st.running": "进行中…",
        "st.ok": "完成",
        "st.fail": "失败",
        "st.skip": "跳过",
        "status.idle": "未连接",
        "status.connecting": "连接中",
        "status.running": "运行中",
        "status.error": "错误",
        "panel.clear_log": "清空日志",
        # ---- 会话流程 ----
        "s.testing": "测试中…",
        "s.connecting": "连接中…",
        "s.auto_port": "自动分配本地端口 {host}:{port}",
        "s.ssh_connecting": "正在连接跳板机 {user}@{host}:{port} …",
        "s.cancelled": "已取消",
        "s.tunnel_ready": "隧道就绪 {host}:{port}",
        "s.probe_via": "通过跳板机探测 {host}:{port} …",
        "s.probe_direct": "直连探测 {host}:{port} …",
        "s.reachable": "目标 {host}:{port} 可达（{ms} ms）",
        "s.test_passed": "测试通过",
        "s.test_done": "测试完成，已断开。",
        "s.fullscreen": "全屏",
        "s.mstsc_started": "mstsc 已启动 (PID {pid})，{addr}:{port}，{size}",
        "s.launch_args": "启动参数：{args}",
        "s.file_mode_hint": "提示：.rdp 文件方式在新版 Windows 上会先弹出安全确认框，可能被本窗口遮挡",
        "s.running": "运行中 · {addr}:{port}",
        "s.mstsc_exited": "mstsc 已退出（code {code}）",
        "s.ssh_dropped": "SSH 连接已断开",
        "s.keep_tunnel": "已配置为 mstsc 退出后保留隧道，等待手动断开…",
        "s.disconnected": "已断开",
        "s.disconnecting": "正在断开…",
        "s.failed": "失败：{msg}",
        "s.tunnel_closed": "隧道已关闭",
        # ---- 错误翻译 ----
        "e.key_passphrase": "私钥已加密，需要口令",
        "e.auth": "SSH 认证失败，请检查用户名、密码或私钥",
        "e.hostkey": "跳板机主机密钥与记录不一致（可能被替换，请检查 known_hosts）",
        "e.ssh_timeout": "连接跳板机超时",
        "e.ssh_connect": "无法连接跳板机: {err}",
        "e.probe_channel": "跳板机无法连到目标 RDP 端口（目标不在线、端口未开放或被跳板机策略禁止转发）",
        "e.probe_timeout": "目标端口连接超时",
        "e.probe_unreachable": "目标端口不可达: {err}",
        # ---- 隧道 ----
        "t.logged_in": "SSH 已登录 {user}@{host}:{port}（{ms} ms）",
        "t.established": "隧道已建立 {bind}:{lport} -> {host}:{port}",
        "t.channel_failed": "打开转发通道失败: {err}",
        "t.rejected": "跳板机拒绝了转发请求",
    },
    "en": {
        "app.title": "Remote Desktop Manager",
        "menu.file": "&File",
        "menu.new": "&New Connection",
        "menu.dup": "&Duplicate Connection",
        "menu.del": "Delete Connection",
        "menu.import": "&Import Config…",
        "menu.export": "&Export Config…",
        "menu.open_dir": "&Open Config Folder",
        "menu.quit": "&Quit",
        "menu.language": "&Language",
        "menu.help": "&Help",
        "menu.open_log_dir": "Open &Log Folder",
        "menu.repo": "&Repository Homepage",
        "menu.changelog": "Version &Info",
        "menu.check_update": "Check for &Updates",
        "menu.about": "&About",
        "chg.title": "Version info  (current v{ver})",
        "chg.check": "Check for updates",
        "chg.close": "Close",
        "upd.title": "Check for updates",
        "upd.checking": "Checking for updates…",
        "upd.countdown": "{sec} s",
        "upd.cancel": "Cancel",
        "upd.close": "Close",
        "upd.download": "Download",
        "upd.latest": "You are on the latest version (v{cur}).",
        "upd.newer": "New version v{latest} available (current v{cur}).",
        "upd.failed_short": "Check failed. Please check your network and try again.",
        "upd.timeout": "No response within {sec} s. Check your network and try again.",
        "tb.new": "New",
        "tb.dup": "Duplicate",
        "tb.del": "Delete",
        "tb.test_port": "Test Port",
        "tb.test": "Test Connection",
        "tb.connect": "Connect",
        "tb.disconnect": "Disconnect",
        "list.filter": "Search name / address / group",
        "panel.title": "Connection Status",
        "status.config_file": "Config file: {path}",
        "tooltip.via_ssh": "via SSH {user}@{host}:{port}",
        "conn.new_name": "New Connection",
        "conn.copy_suffix": " - Copy",
        "conn.unnamed": "Untitled",
        "del.blocked_title": "Cannot Delete",
        "del.blocked_text": "This connection is running. Disconnect it first.",
        "del.title": "Delete Connection",
        "del.text": "Delete \"{name}\"?",
        "save.failed": "Save failed: {err}",
        "validate.title": "Incomplete Configuration",
        "validate.host": "Please enter the target address.",
        "validate.ssh_host": "SSH tunnel is enabled; please enter the jump host address.",
        "validate.ssh_user": "SSH tunnel is enabled; please enter the jump host username.",
        "validate.ssh_key": "Authentication is set to private key; please choose a key file.",
        "ssh_pwd.title": "SSH Password",
        "ssh_pwd.text": "Enter password for {user}@{host}:",
        "quit.title": "Quit",
        "quit.text": "{n} connection(s) still running. Quitting will close all SSH tunnels (remote desktop windows will disconnect). Continue?",
        "about.title": "About",
        "about.text": (
            "<h3>{title} v{ver}</h3>"
            "<p>Manage Remote Desktop (mstsc) connections, optionally through an SSH jump host "
            "using local port forwarding.</p>"
            "<p>Config file:<br><code>{config}</code></p>"
            "<p>Log file:<br><code>{log}</code></p>"
            "<p>Python {py} · PySide6 {qt} · paramiko {pm}</p>"
        ),
        "import.title": "Import Config",
        "export.title": "Export Config",
        "json.filter": "JSON files (*.json);;All files (*)",
        "import.done": "Imported {n} connection(s).",
        "import.failed": "Import failed: {err}",
        "import.mode_title": "Import Mode",
        "import.mode_text": "\"Merge\" appends imported connections to the current list (same ID overwrites); \"Replace\" clears the current list first.",
        "import.merge": "Merge",
        "import.replace": "Replace",
        "export.done": "Exported {n} connection(s) to:\n{path}",
        "export.failed": "Export failed: {err}",
        "tab.rdp": "Remote Desktop",
        "tab.ssh": "SSH Tunnel",
        "f.name": "Name",
        "f.group": "Group",
        "f.group_ph": "Optional, used to group the list",
        "f.notes": "Notes",
        "f.target": "Target",
        "f.target_ph": "Target host IP / domain",
        "f.port": "Port",
        "f.user": "Username",
        "f.domain": "Domain",
        "f.optional": "Optional",
        "f.resolution": "Resolution",
        "f.res_fullscreen": "Full screen",
        "f.res_custom": "Custom…",
        "f.multimon": "Use all monitors (full screen only)",
        "f.launch_mode": "Launch via",
        "f.launch_cli": "Command-line arguments (recommended, no security prompt)",
        "f.launch_file": ".rdp file (more settings, but newer Windows prompts every time)",
        "f.file_only_hint": "Options below apply to .rdp file mode only",
        "f.file_only_tip": "In command-line mode these come from mstsc's own defaults (Documents\\Default.rdp; change them once in mstsc's Options and they persist)",
        "f.clipboard": "Share clipboard",
        "f.drives": "Map local drives",
        "f.smart_sizing": "Scale to fit window (smart sizing)",
        "f.ignore_cert": "Suppress server certificate warning (recommended for tunnels)",
        "f.ssh_group": "Local port forwarding through an SSH jump host (ssh -L)",
        "f.jump": "Jump host",
        "f.jump_ph": "Jump host IP / domain",
        "f.auth": "Authentication",
        "f.auth_password": "Password",
        "f.auth_key": "Private key file",
        "f.key_ph": "e.g. C:\\Users\\me\\.ssh\\id_ed25519",
        "f.browse": "Browse…",
        "f.key_label": "Key file",
        "f.secret_password": "Password",
        "f.secret_passphrase": "Key passphrase",
        "f.secret_ph_password": "Leave empty to be asked on connect",
        "f.secret_ph_key": "Leave empty if the key is not encrypted",
        "f.save_secret": "Save locally (DPAPI encrypted)",
        "f.local_listen": "Local listen",
        "f.auto": "Auto",
        "f.test_port": "Test Port",
        "f.pick_port": "Find Free Port",
        "f.timeout": "Connect timeout",
        "f.timeout_tip": "Maximum wait for connecting, authenticating and opening forward channels",
        "f.seconds": " s",
        "f.keepalive": "Keepalive",
        "f.keepalive_suffix": " s (0 = off)",
        "f.close_with_mstsc": "Close tunnel automatically when the remote desktop window exits",
        "f.key_dialog": "Choose Private Key File",
        "f.all_files": "All files (*)",
        "f.port_auto_result": "Auto mode, currently available {host}:{port}",
        "port.free": "{host}:{port} is free",
        "port.busy": "{host}:{port} is in use",
        "port.denied": "{host}:{port} cannot be bound (permission denied / reserved)",
        "port.error": "{host}:{port} unavailable: {err}",
        "step.port": "Check local port",
        "step.ssh": "Establish SSH tunnel",
        "step.probe": "Probe target RDP port",
        "step.mstsc": "Launch Remote Desktop",
        "st.idle": "Waiting",
        "st.running": "Running…",
        "st.ok": "Done",
        "st.fail": "Failed",
        "st.skip": "Skipped",
        "status.idle": "Not connected",
        "status.connecting": "Connecting",
        "status.running": "Running",
        "status.error": "Error",
        "panel.clear_log": "Clear Log",
        "s.testing": "Testing…",
        "s.connecting": "Connecting…",
        "s.auto_port": "Auto-assigned local port {host}:{port}",
        "s.ssh_connecting": "Connecting to jump host {user}@{host}:{port} …",
        "s.cancelled": "Cancelled",
        "s.tunnel_ready": "Tunnel ready at {host}:{port}",
        "s.probe_via": "Probing {host}:{port} through the jump host …",
        "s.probe_direct": "Probing {host}:{port} directly …",
        "s.reachable": "Target {host}:{port} reachable ({ms} ms)",
        "s.test_passed": "Test passed",
        "s.test_done": "Test finished, disconnected.",
        "s.fullscreen": "full screen",
        "s.mstsc_started": "mstsc started (PID {pid}), {addr}:{port}, {size}",
        "s.launch_args": "Launch arguments: {args}",
        "s.file_mode_hint": "Note: .rdp file mode shows a security prompt on newer Windows; it may be hidden behind this window",
        "s.running": "Running · {addr}:{port}",
        "s.mstsc_exited": "mstsc exited (code {code})",
        "s.ssh_dropped": "SSH connection dropped",
        "s.keep_tunnel": "Configured to keep the tunnel after mstsc exits; waiting for manual disconnect…",
        "s.disconnected": "Disconnected",
        "s.disconnecting": "Disconnecting…",
        "s.failed": "Failed: {msg}",
        "s.tunnel_closed": "Tunnel closed",
        "e.key_passphrase": "The private key is encrypted; a passphrase is required",
        "e.auth": "SSH authentication failed; check username, password or key",
        "e.hostkey": "Jump host key does not match the stored one (possible replacement; check known_hosts)",
        "e.ssh_timeout": "Timed out connecting to the jump host",
        "e.ssh_connect": "Cannot connect to jump host: {err}",
        "e.probe_channel": "Jump host cannot reach the target RDP port (target offline, port closed, or forwarding denied by policy)",
        "e.probe_timeout": "Timed out connecting to the target port",
        "e.probe_unreachable": "Target port unreachable: {err}",
        "t.logged_in": "SSH logged in as {user}@{host}:{port} ({ms} ms)",
        "t.established": "Tunnel established {bind}:{lport} -> {host}:{port}",
        "t.channel_failed": "Failed to open forward channel: {err}",
        "t.rejected": "Jump host rejected the forward request",
    },
}


def _system_default() -> str:
    return "zh" if QLocale.system().language() == QLocale.Language.Chinese else "en"


class _I18n(QObject):
    languageChanged = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._lang = "zh"

    @property
    def lang(self) -> str:
        return self._lang

    def load(self) -> str:
        """从 QSettings 读取上次选择的语言；需在 QApplication 创建后调用。"""
        saved = QSettings().value(_SETTINGS_KEY)
        self._lang = saved if saved in _STRINGS else _system_default()
        logger.info("language: {} (saved={!r}, system={})", self._lang, saved, QLocale.system().name())
        return self._lang

    def set(self, lang: str) -> None:
        if lang not in _STRINGS or lang == self._lang:
            return
        logger.info("language switched {} -> {}", self._lang, lang)
        self._lang = lang
        QSettings().setValue(_SETTINGS_KEY, lang)
        self.languageChanged.emit(lang)

    def tr(self, key: str, **kwargs) -> str:
        table = _STRINGS.get(self._lang, {})
        text = table.get(key) or _STRINGS["en"].get(key) or key
        return text.format(**kwargs) if kwargs else text


i18n = _I18n()


def tr(key: str, **kwargs) -> str:
    return i18n.tr(key, **kwargs)
