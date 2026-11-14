"""The one message catalogue for the web pages, keyed by locale.

Pages never contain user-facing text of their own: they ask a Translator for a key. Adding a language is
adding one dictionary here. What agents read (tool text, API messages) is English and does not come from here.
"""
from __future__ import annotations

from typing import Any

DEFAULT_LOCALE = "zh-TW"

CATALOGUE: dict[str, dict[str, str]] = {
    "zh-TW": {
        "app.name": "Asterism",
        "nav.home": "首頁",
        "nav.messages": "訊息",
        "nav.members": "成員",
        "nav.my": "我的 agent",
        "nav.admin": "管理",
        "nav.logout": "登出",
        "nav.signed_in_as": "{name}",

        "home.title": "首頁",
        "home.projects": "你的專案",
        "home.no_projects": "你還沒有加入任何專案。請向專案成員要一個邀請連結。",
        "home.sign_in_hint": "請先登入。",

        "landing.title": "專案 {slug}",
        "landing.people": "如果你是這個專案的成員，請登入後查看。",

        "login.title": "登入",
        "login.github": "用 GitHub 登入",
        "login.test_heading": "測試模式",
        "login.test_hint": "這台伺服器以測試模式執行：輸入一個 GitHub 登入名，就以那個帳號登入。",
        "login.test_field": "GitHub 登入名",
        "login.submit": "登入",
        "login.failed": "登入沒有完成，請再試一次。",

        "join.title": "接受邀請",
        "join.project": "專案：{name}",
        "join.explain": "加入後你能讀這個專案的內容。",
        "join.for_login": "這個邀請指定給 GitHub 帳號 {login}。",
        "join.button": "加入",
        "join.unusable": "這個邀請已經用過或過期了。請向專案成員要一個新的。",

        "page.title": "{title} · {app}",
        "project.line": "{name} · repo：{repo}",
        "members.github": "（GitHub：{login}）",
        "group.remove_button": "{group} ✕",

        "members.title": "成員",
        "members.people": "人",
        "members.agents": "agent",
        "members.empty": "（沒有成員）",
        "members.permissions": "權限：{list}",

        "col.name": "名字",
        "col.owner": "屬於",
        "col.kind": "種類",
        "col.status": "狀態",
        "col.last_active": "最後活動",
        "col.groups": "身份組",
        "col.github": "GitHub",
        "col.label": "名稱",
        "col.created": "建立時間",
        "col.last_used": "最後使用",
        "col.actions": "動作",
        "col.generation": "綁定世代",
        "col.via": "怎麼授權的",
        "col.connection": "連線",

        "state.online": "在線",
        "state.offline": "離線",
        "state.none": "—",
        "offline.not_bound": "沒有任何 session 登記成它。",
        "offline.no_computer": "它所在電腦的 Asterism 程式沒有連著伺服器（程式沒在執行，或電腦離線）。",
        "offline.session_closed": "它所在電腦的程式連著伺服器，但它的對話已經關閉，叫不醒；重新開啟那個對話就會回來。",
        "offline.no_subscription": "這是經由 ChatGPT 連接器加入的 agent，沒有有效的事件訂閱：它只有在自己呼叫工具時才拿得到訊息。要讓它叫得醒，請到「我的 agent」頁產生邀請連結傳給它。",
        "offline.unanswered": "送給它的訊息兩次都沒有確認收到，所以記成離線；它一呼叫工具就回到在線。",
        "offline.silent": "它有重要訊息沒回，而且一整段提醒時間都沒有活動；它一呼叫工具就回到在線。",

        "group.owner": "擁有者",
        "group.human": "人類",
        "group.ai": "AI",
        "group.ownership": "{owner} 的 agent",

        "perm.read": "讀取",
        "perm.post": "發言",
        "perm.create_channel": "建立頻道",
        "perm.create_schedule": "建立排程",
        "perm.assign_tasks": "指定任務",
        "perm.manage_own_agents": "管理自己的 agent",
        "perm.edit_tasks": "編輯任務",
        "perm.manage_members": "管理成員",
        "perm.manage_groups": "管理身份組",
        "perm.project_settings": "專案設定",

        "kind.claude-code": "Claude Code",
        "kind.codex": "Codex",
        "kind.chatgpt": "ChatGPT（dot）",
        "kind.other": "agent（未指定種類）",
        "cred.computer": "電腦",
        "cred.connector": "連接器",

        "my.title": "我的 agent",
        "my.agents": "我的 agent",
        "my.no_agents": "你還沒有 agent。",
        "my.credentials": "電腦和連接器的憑證",
        "my.no_credentials": "你還沒有授權任何電腦或連接器。",
        "my.revoke": "撤銷",
        "my.remove_agent": "移除",
        "my.add_group": "加入身份組",
        "my.add": "加入",
        "my.remove_group": "移出 {group}",
        "my.via.invite": "邀請連結",
        "my.via.device": "瀏覽器裡同意",
        "my.via.connector": "連接器授權",
        "my.connected.yes": "程式連著",
        "my.connected.no": "程式沒有連著",

        "invite.title": "邀請 agent",
        "invite.skip": "邀請 agent 是讓你電腦上的 Claude Code 或 Codex 加入這個專案。如果你不帶 agent，只看 repo、參與討論，可以跳過這一步。",
        "invite.button": "產生邀請連結",
        "invite.say": "把這句話貼給你的 agent：",
        "invite.expires": "這個連結只能用一次，{time} 前有效。",
        "invite.self": "或者自己先設定這台電腦（在終端機執行，選你用的產品）：",
        "invite.system.macos-linux": "macOS 或 Linux",
        "invite.system.windows": "Windows（PowerShell）",
        "invite.product.claude-code": "Claude Code",
        "invite.product.codex": "Codex",
        "invite.copy": "複製",
        "invite.copied": "已複製",
        "invite.unavailable": "Asterism 的程式還不能從這台伺服器下載，所以暫時不能自己設定電腦。",
        "my.switches": "我的 agent 的開關",
        "my.switches_hint": "這些開關決定別人能對你的 agent 做什麼，預設全部關閉。",

        "switch.others_mention": "別人可以 @ 我的 agent",
        "switch.others_channel": "別人的頻道訊息會送到我的 agent",
        "switch.others_assign": "別人可以指定任務給我的 agent",
        "switch.others_regroup": "別人可以調整我的 agent 的身份組",
        "switch.later": "（之後的版本才生效）",

        "device.title": "授權一台電腦",
        "device.ask": "電腦「{computer}」上的 {kind} 要以你的名義加入專案「{project}」。",
        "device.code": "確認碼：{code}",
        "device.enter_code": "輸入 agent 顯示的確認碼",
        "device.lookup": "查看",
        "device.approve": "同意",
        "device.deny": "拒絕",
        "device.warning": "只有在你剛剛自己要 agent 加入時才按同意。",
        "device.status.approved": "這個請求已經同意了。",
        "device.status.denied": "這個請求已經拒絕了。",
        "device.status.expired": "這個請求已經過期。請讓 agent 重新提出。",
        "device.done.approve": "已同意。agent 會自己完成剩下的步驟。",
        "device.done.deny": "已拒絕。",

        "consent.title": "授權連接器",
        "consent.ask": "「{client}」要以你的名義存取專案「{project}」。同意後會回到 {host}。",
        "consent.not_member": "你不是這個專案的成員，不能授權連接器。",
        "consent.untrusted": "這個連接器沒有在這裡註冊，或它要回到的位址不是它註冊過的。請在 ChatGPT 裡從頭新增連接器。",
        "consent.bad_resource": "這個請求沒有指明是哪一個專案。請在 ChatGPT 裡從頭新增連接器。",

        "admin.title": "管理",
        "admin.invite": "產生邀請連結",
        "admin.invite_login": "指定對方的 GitHub 登入名（可留空）",
        "admin.invite_button": "產生",
        "admin.invite_hint": "邀請只能用一次，七天內有效。被邀請的人能經由平台讀這個專案和它的 repo。",
        "admin.members": "成員和身份組",
        "admin.remove": "移除",
        "admin.add_group": "加入身份組",
        "admin.add": "加入",
        "admin.remove_group": "移出 {group}",
        "admin.agent_of": "{owner} 的 agent",

        "confirm.remove": "確定要移除 {name} 嗎？",
        "confirm.revoke": "確定要撤銷這份憑證嗎？用它的 agent 會立刻失效。",

        "msg.title": "訊息",
        "msg.channels": "頻道",
        "msg.private": "私訊",
        "msg.channel_name": "新頻道的名字（小寫英文、數字、-）",
        "msg.new_channel": "建立頻道",
        "msg.choose_member": "選一位成員",
        "msg.start_private": "開始私訊",
        "msg.my_agent": "{name}（我的 agent）",
        "msg.settings": "頻道設定",
        "msg.settings_private": "私訊沒有頻道設定。",
        "msg.mute_me": "我：沒有 @ 我的訊息一律靜音",
        "msg.mute_agent": "{name}：沒有 @ 它的訊息一律靜音",
        "msg.older": "載入更早的訊息",
        "msg.empty": "這裡還沒有訊息。",
        "msg.private_with": "和 {name} 的私訊",
        "msg.reply": "回覆",
        "msg.replying_to": "回覆 #{id}",
        "msg.reply_to_link": "回覆 #{id}",
        "msg.reply_cancel": "取消回覆",
        "msg.input_label": "訊息內容",
        "msg.input_hint": "Enter 送出，Shift+Enter 換行。可用 Markdown 和數學式（$...$、$$...$$）。",
        "msg.send": "送出",
        "msg.system": "系統",
        "msg.kind_agent": "agent",
        "msg.important": "重要",
        "msg.unread": "{n} 則未讀",
        "msg.not_here": "訊息 #{id} 不在這裡。",
        "msg.sent_offline": "已送出。{names} 現在離線，回來後會收到。",
        "msg.sent_closed": "已送出。{names} 的主人沒有開放別人 @，所以不會叫醒它。",
        "msg.sent_unknown": "已送出。沒有叫「{names}」的成員或身份組。",
        "msg.saved": "已儲存。",

        "error.title": "出了問題",
        "error.not_found": "找不到這個頁面或項目。",
        "error.forbidden": "你沒有權限做這件事。",
        "error.not_member": "你不是這個專案的成員。請向專案成員要一個邀請連結。",
        "error.not_signed_in": "請先登入。",
        "error.gone": "這個項目已經用過或過期了。",
        "error.conflict": "這個動作和現況衝突（例如名字已經有人用了）。",
        "error.superseded": "這個 session 已經被接手。",
        "error.invalid_name": "名字只能用英文字母、數字、「.」「_」「-」，最多 40 個字。",
        "error.generic": "沒有完成（{code}）。",
        "error.too_long": "訊息最多 4,000 個字，請分成幾則，或放進 repository 的檔案。",
        "error.bad_request": "內容不對，請檢查後再試。",
        "done.saved": "已儲存。",
    },
}


class Translator:
    def __init__(self, locale: str = DEFAULT_LOCALE):
        self.locale = locale if locale in CATALOGUE else DEFAULT_LOCALE
        self.table = CATALOGUE[self.locale]

    def __call__(self, key: str, **kw: Any) -> str:
        """A missing key fails loudly rather than leaking a key or an untranslated string onto a page."""
        text = self.table.get(key)
        if text is None:
            text = CATALOGUE[DEFAULT_LOCALE][key]
        return text.format(**kw) if kw else text

    def has(self, key: str) -> bool:
        return key in self.table or key in CATALOGUE[DEFAULT_LOCALE]

    def group(self, name: str, kind: str, owner: str = "") -> str:
        """Default groups have a display name; the others show as they are named."""
        if kind == "default" and self.has(f"group.{name}"):
            return self(f"group.{name}")
        if kind == "ownership" and owner:
            return self("group.ownership", owner=owner)
        return name

    def js_messages(self) -> dict[str, str]:
        """The texts the page script needs, sent along with each page."""
        keys = [k for k in CATALOGUE[DEFAULT_LOCALE] if k.startswith(("error.", "done.", "confirm.", "msg.", "invite."))]
        return {k: self(k) for k in keys}


def pick_locale(accept_language: str | None) -> str:
    """The first locale in Accept-Language that the catalogue has; otherwise the default."""
    for part in (accept_language or "").split(","):
        tag = part.split(";")[0].strip()
        for loc in CATALOGUE:
            if tag.lower() == loc.lower() or (tag and loc.lower().startswith(tag.lower() + "-")):
                return loc
    return DEFAULT_LOCALE
