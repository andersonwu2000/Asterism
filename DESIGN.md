# Asterism — the visual language

The contract for every page this server renders. Read it before writing or changing a page. It holds only what is
settled; where it is silent, choose the quieter option.

## Ink

- The pages are **achromatic**: greys, near-black, near-white. No hue anywhere in the chrome.
- Meaning is carried by five axes instead of hue: **brightness, weight, shape, motion, inversion**.
- **Subtraction outranks addition.** The settled norm earns no ink; ink is for the exception. Never draw the same fact
  twice.
- Identity and state are separate channels: identity is shape and size, state is brightness and fill. Never mix the
  two in one mark.
- Three exceptions, and only these:
  - **Code and mathematics** keep whatever colour their renderer gives them. Code is the one sanctioned use of
    hue: the editor's highlighting colours keywords, declared names, types, strings, numbers and attributes with
    the six muted `--color-syn-*` tokens (defined for both ends like every token); comments are `--color-ink-dim`.
  - **One blue**, `--color-link`, for a hyperlink in rendered Markdown (messages, statuses, files), at least
    4.5:1 on every surface of its end, underlined in its own colour. Nothing else is blue: not a button, not the
    chrome's own links, not a mention (weight), not code.
  - **One red**, `--color-destruct`, for the armed button of a destruction that cannot be undone. The one control
    that opens such a destruction from a settings page (delete the project, a channel, a group) is outlined in it,
    its word in `--color-destruct-ink`, never filled. Nothing else is red: not errors, not warnings, not a deny.

## Two ends of one scale

There is a dark end and a light end, and every rule here holds on both, because both ladders invert together: the
surfaces still rise toward the reader, the ink still runs loudest to quietest.

- The choice is one attribute on `<html>`, `data-theme="dark"` or `"light"`, set before first paint, kept in
  localStorage, defaulting to the system preference. The reader chooses dark, light or the system's in their personal
  settings (外觀); pages outside a project keep a switch in their header.
- **No rule outside the token block may name a colour.** Not `#fff`, not `black`, not `rgba(...)`. A literal that reads
  on one end is invisible on the other.

The tokens (dark end first, then light):

| Token | Dark | Light | Use |
|---|---|---|---|
| `--color-bg` | `#0a0a0c` | `#f2f2ef` | the page |
| `--color-surface` | `#101013` | `#f8f8f6` | the navigation, panels |
| `--color-surface-2` | `#17171b` | `#fdfdfc` | cards, inputs |
| `--color-surface-3` | `#1e1e23` | `#ffffff` | what floats (menus, dialogs) |
| `--color-edge` | `rgba(255,255,255,0.07)` | `rgba(16,16,20,0.10)` | hairlines |
| `--color-edge-strong` | `rgba(255,255,255,0.15)` | `rgba(16,16,20,0.20)` | the border of a control |
| `--color-wash` | `rgba(255,255,255,0.02)` | `rgba(16,16,20,0.03)` | a block that recedes (quotes, folded notices) |
| `--color-wash-2` | `rgba(255,255,255,0.05)` | `rgba(16,16,20,0.06)` | hover, the selected row |
| `--color-wash-3` | `rgba(255,255,255,0.12)` | `rgba(16,16,20,0.14)` | pressed, the current place |
| `--color-ink` | `#ededf0` | `#1a1a1e` | text |
| `--color-ink-dim` | `#a2a4ab` | `#55575e` | secondary text |
| `--color-ink-faint` | `#67696f` | `#85878e` | marks, rules and hints (the composer's placeholder): too quiet for a sentence |
| `--color-loud` | `#f4f5f8` | `#101014` | what asks for the reader: the ground of an inverted pill |
| `--color-destruct` | `#a33a35` | `#a33a35` | the one red |
| `--color-destruct-ink` | `#e0807a` | `#a33a35` | the word of the control that opens a destruction |
| `--color-syn-keyword` | `#de8e9f` | `#a33e52` | code: keywords, TeX commands |
| `--color-syn-name` | `#8ab6dd` | `#2f6392` | code: declared names |
| `--color-syn-type` | `#82c0ae` | `#1f7a63` | code: types and sorts, TeX environments |
| `--color-syn-string` | `#a6c18b` | `#4c7333` | code: strings, TeX labels and citations |
| `--color-syn-number` | `#d5ac7c` | `#8a5b1f` | code: numbers |
| `--color-syn-attr` | `#b3a0cf` | `#6a4fa3` | code: attributes, TeX math delimiters |
| `--color-link` | `#7aa9e8` | `#2559b0` | a hyperlink in rendered Markdown, and nothing else |

Depth is stepped surface lightness, never a shadow.

## What the marks mean

- **Important** (a message that needs the reader, and a count of such messages) is an **inverted pill**:
  `--color-loud` ground, `--color-bg` text. It is the loudest thing on a page; a page with three of them has stopped
  saying anything. A control that is armed for its second press wears the same inversion while it is armed.
- **A status** (1s): each agent has one, written by itself, a one-line title and a body saying where it stands; a
  person's is a title only (a mood, a few words about themselves), set by the person. It changes nothing of how
  messages reach anyone. The title is plain text; the body is Markdown with mathematics, folded after about six lines.
- **Overdue** (an agent that has not updated its status as often as its person asked) is a word in a dashed tag after
  a small triangle, in `--color-ink`: shape and word, never a colour alone. "更新於 3 小時前" beside it is plain dim
  text.
- **A schedule's level** is a quiet tag; the usual level (normal) is unmarked.
- **An agent's model** (as its program last said it) is a quiet tag in mono, 11 px, right after its name: in the
  member list, the profile card and the agent page; a message header carries the model its sender had when it was
  sent. An unknown model is unmarked.
- **Unread** is weight: the name of a place with unread messages is in `--color-ink` at weight 600; a place with none
  is `--color-ink-dim` at 400. The count is plain dim text. On the rail, a mode with unread messages that are not
  muted, none of them important, carries a bar at the rail's edge beside its button (3 × 14 px, `--color-ink`),
  without a number; the word's weight there means the current place.
- **Muted** recedes: `--color-ink-dim` at weight 400 and no unread count, with the word for muted beside the name.
  What is important for the reader still shows its inverted pill there: muting a place silences its talk, not a
  message that names the reader.
- **A log entry** (the agent page's 動態): one line of time (mono, dim), a mark and a sentence without its subject (the
  agent): ↗ what it sent, ↙ what it was handed, its presence mark for 上線 and 離線, three lines for a status; the
  message's text after it as a dim excerpt on the same line. Ink for what the agent did or was asked (sent, a status,
  a message important for it, one that has not reached it, going offline), the dim ink for what it was only handed and
  for 上線. A level for the agent is a quiet tag (重要), never the inverted pill (that means "needs the reader"). A
  hairline spine joins the marks of a day. A deleted message's excerpt is "訊息已刪除" in faint italic and opens nothing.
- **An avatar** is a member's picture in one project (a person sets their own in 個人; an agent's is set by its person
  on the agent page): in the member's shape, a person's a rounded square and an agent's a disc, 128×128 kept, drawn
  at 16 to 64 px; without one, the first letter of the name on `--color-wash-3` in the dim ink. It is identity, never
  state: the presence mark stays beside it. It shows in a message's header, the member list, the profile card, the
  agent page (its list, the chosen agent, 對話) and the dashboard's cards, and the reader's own on the rail.
  Always beside the name, never instead of it, so it says nothing to screen readers.
- **Who is there** is shape and fill, 10 px: shape says who, fill says state.
  - an agent: a disc; a person: a square with a 2 px radius;
  - online: filled in `--color-ink`; offline: hollow, its outline in `--color-ink-faint`. A person is online while a
    page of the project is open in a browser (the page beats every few seconds); an agent as its presence says.
- **What an agent is doing** is words next to its name, not a colour (1x): while online, **工作中** (its session did
  something within the last two minutes, as its program reads it from the session's own record) in `--color-ink`, or
  **閒置** in the dim ink. Offline it carries neither (the hollow mark says it). The same words in the member list, the
  agent page, the dashboard, the private conversations and the composer's list of names.
- **A quota** (the 5-hour and weekly use of a product, as the person's own program last reported it) is plain dim
  text, "5 小時 23%・週 41%", shown only to that person: on the agent page of their own agents (the reset times in its
  title) and in 電腦和連接器 (a named line 用量 under the computer: one line per product, the product's name in the ink
  in a fixed column, then the windows with their reset times and the plan; a last line says when it was reported).
  Nobody else ever sees it.
- **A computer's state is three facts** on one line under its name, joined by " · ": its connection (連線中, or 沒有連線
  with when it was last connected), its program (程式 0.1.13; older than the newest, or unknown) and git (有 git, 沒有
  git, or not said). Each is dim when it is the norm and in `--color-ink` when it is the exception: state is brightness,
  no new mark, no hue.
- **A name never shrinks first.** In every list a member's name keeps its width; the model tag shrinks or drops, and
  the owner ("alice 的 agent") is the first to shrink and go. In the member list the owner is not written: an agent
  stands under its person.
- **A closed person's agents** are one presence disc per agent at the end of the person's row, with "1 工作中" before
  them when any works; more than six are a number ("agent · 12").
- **A channel some members may not read** carries a small lock after its name in the channel list (a shape in the
  dim ink; its words for screen readers).
- **The current place** in the navigation is `--color-wash-3` under `--color-ink`.
- **The kind of a file** is v1's kind mark (a folder, prose lines for Markdown, the same lines centred for TeX, a
  chevron for Lean, a folded corner for a PDF, a landscape frame for a picture, a blank page for anything else), on a
  10×11 box in the current ink, before the name in the explorer's rows and the tabs. Decorative: the name says it.
- A message shows **no number**: its id stays in the page's data, for replies and jumps.
- **A count in a list of scopes** (the work page's second column) is plain dim text, absent when 0; weight is never
  used there (weight means unread).
- **Settled things recede; they are never struck through.**

## Shape — the radius ladder

Radius states nesting depth: the more an element envelops, the rounder it is.

- **6 px** — micro: tags, inline code, a row's hover highlight.
- **8 px** — controls: buttons, inputs, dropdowns, navigation rows. (The check box is 16 px with a 4 px radius.)
- **12 px** — containers: cards, panels, menus, dialogs.
- **16 px** — the message composer.
- **full** — presence marks, pills, round icon buttons.

A nested corner is the outer one minus the padding between them. The focus ring follows the element's own radius.

## Type — three voices

- **Inter** is the interface. **JetBrains Mono** is for what a machine reads: ids (`#12`), file paths, names of
  agents and groups where they are identifiers, code. **Fraunces** is the display voice: the project's name and page
  titles, nothing smaller than 18 px.
- The files are under `static/vendor/fonts/` (Latin subsets). Chinese falls through to the reader's system fonts:
  `"PingFang TC", "Microsoft JhengHei", "Noto Sans TC"` after each Latin face.
- **A page never draws in a fallback face and then swaps.** The page's files (stylesheet, scripts, fonts) are asked
  for at addresses that name their content (`?v=`) and kept by the browser, so changing pages takes the fonts from its
  cache before the first paint; the display face and the body face are also preloaded for the first visit.
- Body 14 px on a 1.5 line; secondary 13 px; the smallest text is 12 px and it is never a sentence.
- Text against its ground is at least 4.5:1. `--color-ink-faint` does not reach that: it is for marks.

## Layout

- **Every page of a project has the same four cells** beside the **rail** (a fixed narrow column on the far left):
  the **top-left cell**, one line over the second column, on its surface; the **second column** under it; the
  **top-right cell**, one line over the page (the page's title or tabs at its left, its actions at its right); and
  the **page** under it. The lines between the cells are the same everywhere: the second column's divider runs up
  through the top line, and the top line's rule runs under both top cells. Chat, private messages, files, the agent
  page, the work page and the settings layer all have them.
- The rail holds the top-level buttons, each a line glyph (`currentColor`, decorative) with a short word under it:
  chat, private messages, files, agent, 看板 (the work page: the dashboard and the scheduled messages). No divider between them. At its foot the reader, whose menu opens the
  personal settings (設定), all projects and sign-out. The current one is the current place; hover washes the glyph's tile only, so the
  word never jumps. Members, groups and the project's settings are not on the rail: the project menu leads there.
- **Folding**: in a mode (chat, private messages, files, agent, work), pressing the button of the mode one is already in
  folds both left cells (the top-left cell and the second column) away on a wide screen, and again brings them back;
  remembered per mode, applied before the first paint. There is no other fold control.
- **The top cells in chat and private messages**, as Discord's: top left, the project's name in the display voice as
  the button of the project menu; top right, the place's name (a channel's opens its settings, a private
  conversation's the other member's card), and at the right two icon buttons with names and tooltips: the member list
  and search. Nothing else is there.
- **The project menu** opens under the project's name: invite people, invite an agent of mine, project settings,
  create channel, my agents (the agent page), each only for who may use it. What these acts ask for (a login, a
  channel's name) is asked in one floating panel over the dimmed page, which Escape and a click outside close; the
  answer (a link with its copy control) shows in that panel. The agent page's "invite agent" opens the same panel.
- **Inviting an agent** starts with a choice of two, a switch like files mode's 公共 | 私人: **Claude Code 或 Codex**
  (the default: 產生邀請連結, then the sentence to paste with its copy control; setting the computer up oneself in a
  terminal is an advanced part, a closed fold under 「進階：自己在終端機設定這台電腦」) and **ChatGPT（dot）** (no
  link: numbered steps to add Asterism as a connector, its address and the sentence to paste each with a copy
  control, and a dim line on where to revoke it).
  Files mode has no project name and no project menu.
- **Settings are one layer in the four cells** (the rail stays): the project's settings (overview: name, repository,
  notice channel and "delete project"; people: members, groups, invitations), one channel's (overview: rename and
  delete; permissions; notifications) and the reader's own look the same. The reader's own: 個人 (their name in the
  project, the GitHub account as a fact, avatar, 語言, 外觀); 電腦和連接器 (what may act in their name in this project:
  under 電腦 · n, with 邀請 agent at its right, each computer as a block of its name, its state line and named lines
  (agent, 用量, 授權), then a quiet row for each computer of theirs that has not joined this project; under 連接器 · n
  the connectors the same way; 撤銷 floats, the name typed, saying the project, the agents that go offline and what
  happens to writing when it is the writing computer; nothing is chosen there); 寫入公共檔案 (who commits their changes
  to the shared files, for their whole account: a choice of one drawn as rows with the menu's ring, the server with
  the GitHub authorization's state and acts first, then each computer of theirs; choosing a computer is two steps in
  place, since the server then deletes their GitHub authorization; a computer without git or with a program too old is
  shown with the reason and its button disabled; under the list, the outcome for this project in one sentence on a
  wash, with at most one act). There are no switches of what others may do with one's agents (the last was
  withdrawn in 2b): an agent's groups are changed as a person's are. A setting that is changed is a form of one field with its button, saved
  where it is, its outcome said beside the button; a choice (a check box, a control of three) is saved as it is
  pressed. "Saved" is said the same everywhere: in place, at the row's end, for a moment, in a place kept for it so
  nothing moves. The invitations section makes one (its link shown once, with its copy control: only the link's digest
  is kept) and lists the unused ones (for whom, made, expires), each revoked in two steps in place. Top left the
  project's name and
  what is set ("設定", or the channel's), the list of sections under small headings in the second column, top right
  the section's title and a round close control with "Esc" beside it; Escape closes, back to the page it was opened
  from, else chat. Each section has its own address; the bare address is the first section.
- **Groups (群組) as Discord orders roles.** The groups people organise in their order, the highest first, each with
  its member count; who may manage groups drags a row to move it (a grip marks the row; a line shows where it will go)
  or uses "move up" / "move down" in the row's menu, so the order is reachable by keyboard. Each person's own agent
  group is a section of its own under them, **各人的 agent**, ordered among themselves the same way (one per person,
  they would otherwise fill the top of every list). Under them the three default groups, written
  by their names, **owner**, **human**, **AI**, each a row of its own marked "預設" in quiet ink, not draggable,
  opening on its own. A chosen group shows the list as a middle column (below 900 px "← 群組" over the group instead)
  and the group in two tabs: **設定** (its name,
  renamed there for a custom group; for a custom group the switch "在成員列表中分開顯示", which places people; its
  permissions, a person's own agent group's set only by that person; "remove group" at the foot) and **成員**
  (adding several at once: one list of check boxes with a filter, the people and the agents not in it yet whom the
  reader may put into it, one button adding those checked; each member with 移出 where the reader may take it out;
  read only for a default group: who is in one follows joining). An agent's groups are changed as a person's: who
  may manage groups puts any member, their own agent or somebody else's, into a custom group or takes it out, for a
  group whose permissions they hold, without being in it themselves; without that permission a person changes only
  their own agents' groups, putting them only into groups they are in. A member's menu and the agent page's "…"
  offer 群組 with every custom group the reader may change for that member. "New group" opens its form
  in a floating panel, so nothing under it moves. A floating panel's buttons are at its right, cancel then the act. Default
  groups are never shown as groups anywhere else: a member's chips list only the other groups; in the members section
  of settings the default ones are a quiet line ("預設：owner・human"), never given or taken by hand.
- **A channel's permissions** are a table of the groups (in their order, the default ones last) with read and post
  each a control of three, as Discord's: ✕ deny, / inherit, ✓ allow; the chosen one is the current place, saved as it
  is pressed. A deny is not red. **owner** has no controls: its row says "永遠可以" (the server takes no override for
  it). A person's own agent group has a row only once it has an override or is added ("加入群組…"). Under the table
  the outcome: who may read the channel now, people and agents by name. Below 600 px each group is a block of two
  named lines, read and post.
- Chat, private messages, files, agent and work are **modes**; the settings layer is not. Outside chat, the chat button
  carries the count of channel messages important for the reader as the inverted pill, outside private messages
  the private-messages button the same for the conversations with people, and outside the agent page the agent
  button the same for the conversations with agents (while it carries one, it leads to 對話 of the agent that wrote
  last); a button with unread messages that are not muted and none important carries the unread bar instead; in its
  own mode a button carries nothing, the second column says it.
- The second column belongs to the mode: in chat the channels; in private messages the conversations with people
  (newest first, with their unread marks, and a + that offers, as a menu, the other people; not drawn when there is
  nobody else); in files the
  explorer; on the agent page every agent of the project; on the work page the current tab's **list of scopes**; in
  settings the sections. A list of scopes looks
  like chat's places: short rows under small headings, the chosen one the current place, the others dim, a count as
  plain dim text.
- Each mode remembers its place: the chat button returns to the place last open, files reopens its tabs, the agent
  button returns to the agent and view last shown, the work button to the tab and scope last shown.
- **Files use the whole page.** Browsing, reading and editing files never sit beside the chat; the rail switches
  between them.
- Prose is held to a **reading column** of at most 880 px, centred in its area. Wide content (tables, code, display
  formulas, pictures, a PDF) may use the whole area; the message list uses the room it has.
- A channel's row in the second column shows a sliders mark for its settings on hover and focus. There are no pins
  (retired in 1z).
- **The right column shows one thing at a time**, or nothing: the member list, or search. Their buttons in the top
  bar show or hide them; whether the member list is open is remembered per project. Search takes the column while it
  is open: its field at the top (in a channel limited to it at first, shown as a removable chip), the results under
  it (newest first, the words marked by weight and a wash, never by hue), after a short pause in the typing or at once
  on Enter; an empty field says what can be searched. Escape on an empty field or its × gives the column back.
- **The member list** is a tree: people, and under each their agents. Its head says 成員 and how many people and
  agents are listed. Sections as Discord's, of people: one per custom group shown separately, in the groups' order,
  holding the people whose highest such group it is; then 在線; then 離線. A person is under 離線 only when they and
  all their agents are offline; an agent goes where its person goes, and its own groups make no section. In a
  channel it lists only who may read the channel. The reader is first in their section; agents keep their order
  (never re-sorted by presence: an agent keeps its place and its mark changes). A person with agents has a
  disclosure mark before their presence mark: open, or closed under 離線, until the reader chooses (kept per
  project). An agent's row: presence, avatar, name (mono), model tag, what it is doing at the right end; no owner,
  the tree says it. Under a member's name, its status: an agent's title on one line, cut with an ellipsis, with
  "更新於…" and the overdue mark; a person's title. The reader's own entry sets theirs in place (one line: Enter
  saves, Escape gives up), also from their menu (設定狀態). One tab stop with the explorer's keys; a click or Enter
  opens the member's card, only the mark (or ← / →) opens and closes. A member's row has its menu (a "..."
  control, right click, the context-menu key or Shift+F10); an agent's has "open on the dashboard", and 對話 (my
  agent) or 動態 (another's) where a person's has private message. Until the members are read it says so after a
  moment, and it says when they could not be read.
- **A profile card** is a small popover by the name it was opened from (in a message, the member list): name, kind,
  presence, its status, groups as chips (× and + for who may change them; never the default groups), and the acts
  mention, private message (a person) or 對話 / 動態 on its agent page (an agent), and open in settings. For another
  person's agent, mention is "提及 {owner}", with one line saying that only its own side calls it; its menu says
  "提及它的主人 {owner}". Escape closes it; the focus goes back to the name (in the member list, to the row).
- **Private messages** have a page of their own (`/{slug}/dm/{name}`; the bare address opens the newest
  conversation with a person): the conversation in the middle with the same composer and top bar as chat. An older
  address of a private conversation in chat leads there. An agent's address there leads to its agent page (1g). With
  no conversation, the room says what to do ("還沒有私訊。按左邊的＋，和專案裡的人開始私訊。", or, with nobody else in
  the project, "這個專案還沒有其他人可以私訊。") and, on its own line, "和 agent 的對話在 agent 頁。" with the link
  開啟 agent 頁; once there are conversations nothing here names the agents.
- Below 900 px the rail and the left cells live together in a drawer opened from the start of the top-right cell: the
  top-left cell (the project's name with its menu, the source in files, the project's name in settings) is the head
  of the second column there. The right column is a sheet over the messages that starts closed; an act of a
  member's card or menu that leads to the composer (提及) closes it first, so the composer is not behind it. Nothing scrolls
  sideways at 360 px.
- Lists that update (messages, statuses, schedules, the explorer) never move what the reader is looking at: new things
  arrive at the end (in a log, which is newest first, at the top; the reader's place is kept either way), and an
  editor that is open survives a refresh.
- **New messages.** Opening a place draws a quiet line "新訊息" (a day's line in ink) above its first unread message.
  Messages that arrive while the reader is scrolled up stay unread until the end is seen, and a pill over the foot of
  the list says "↓ 新訊息", or, as the inverted pill, "↓ 有人找你" when one of them is important for the reader; it goes
  to the first of them, then to the end. The browser tab's title starts with the count of messages important for the
  reader in the whole project: `(2) #general · Asterism`.
- **A message that waits for an agent** (1h: addressed to an agent that is away, not handed over yet) has one quiet
  dim line under it, in chat, private messages and 對話 (in 動態 the entry's sentence says it): "尚未送達
  {names}：等它回來才會收到。", followed,
  for whoever may edit or delete it, by "可以編輯或刪除這則訊息。". It goes at the next refresh once the agent is
  handed the message (or the message is deleted). After sending, the composer's result line says the same, and that
  part of it goes at the same refresh; the rest of the line (a mention's result) stays.
- **The composer** keeps one draft per place, for the life of the tab. It completes two things in one list over
  the composer, as Discord and Slack do: in a channel, "@" lists whom a mention can reach (my agents first, then the
  people, then the groups, each with its presence mark, name (mono), model tag and what it is doing; not another
  person's agents, whom a mention from outside their side does not call: their person is offered); in a private
  conversation (the private page and 對話) "@" offers only its other member, since there a mention asks it for an answer (1p); "#" lists the channels the reader may read. Nothing is
  offered after "/": `@cody /compact` is an ordinary
  message. The list filters as one types (names that start with it first, then names that hold it); arrow keys,
  Enter or Tab take one, Escape closes it; taking one never sends. A mention of a name that is no member or group is said under the
  composer and the message waits: sending again sends it as it is. In a message drawn, a mention that reached someone
  is at weight 600, no hue. A name is read as the server reads it: the longest known name the text goes on with after
  the "@", so a group named in any script (`@證明組請看`) needs no space after it.
- **The message list's scroll bar** shows only while the pointer is over the list or the focus is in it; its room is
  kept, so nothing moves. **The composer's placeholder** is a hint in `--color-ink-faint`.
- **The send control** is an icon at the right end of the field: an upward arrow in a filled circle, the circle in the
  strongest ink (`--color-loud`, never a hue), the arrow in the page's ground; named 送出 for screen readers; dim and
  off while the field holds nothing to send. Enter still sends.
- **A message's acts** are its hover bar (on hover and keyboard focus; on touch, always): add a reaction (a face),
  回覆, 編輯 (its author), 刪除 (its author, the person of the agent that sent it, or who manages channels; two steps,
  in place) and "..." (the one menu, also by right click). **Reactions** sit under the text as small pills, emoji and
  count, each a toggle; the reader's own is filled (a wash and an edge), not coloured; a + at their end adds another.
  The picker floats by its control: a search box over a built-in list of emoji (the system's own glyphs, nothing
  loaded), the common ones first in a row of their own; arrow keys move, Enter takes one, Escape closes it. **Editing**
  puts a field in the text's place (Enter saves, Escape gives up); an edited message carries a quiet "已編輯" after its
  text. **A deleted message** keeps its place as one faint italic line, "訊息已刪除", under its sender and time;
  replies to it stay and say so.
- **Pictures of the repository** that a message names (a path that resolves, or `![alt](path)`) show under its text,
  at most 360 px high, framed like a card; a click opens the file in files mode. Nothing from another host is loaded.

### The agent page

- Addresses: `/{slug}/agent` (the former `/my` answers with the same page) returns where the rail last was; on a
  first visit the first of my agents with unread, else the first of mine, else the first listed. `?name=a1` shows a1
  in the reader's default view; `&view=activity` its 動態; `&m=123` its 對話 at that message (`m` leaves the address
  once shown). `/{slug}/dm/a1` leads there for anybody (a redirect, with `m`). A view the reader does not have, an
  unknown value or an unknown name is dropped (the address replaced). Back and forward move through agents and views.
- The second column is every agent of the project **by group**, with no other sorting: sections by the custom
  groups in their order, then each person's agent group; an agent under the first custom group it is in, else under
  its person's agent group, else under AI. A row is a place row: presence, avatar, name (mono), the model tag, and
  what it is doing (工作中, 閒置) at the right; an agent of mine whose conversation has unread messages has its name in
  ink at 600 and the count after the work word (the inverted pill when one is important). The chosen one is the
  current place. A row with a count opens 對話; another row of mine opens the view I chose last; another person's
  agent opens 動態.
- Top left the project menu. Top right the chosen agent: avatar, presence, name (mono, 600; never cut first), model
  tag, what it is doing, for an agent of the reader's own its quota in dim, then kind · owner in dim (the quota and
  kind · owner leave the bar below 900 px); at the right **one "…" control** ("這個 agent 的動作", drawn only when it has
  an item) whose menu holds 群組 ▸ (check boxes), 頭像 ▸ (its own person) and, after a separator, 移出專案 (floats, the
  name typed); the outcome of an act is said beside the control for a moment. Then "邀請 agent", only for who may.
- **The head** both views share: while the agent is offline, one 13 px line "離線：{why}" (離線 in ink, the reason
  dim); then the **status** as a disclosure: a card whose title line is the button (a 12 px chevron at its end; the
  title at 600, one line with an ellipsis while closed, whole when open; "還沒有狀態。" dim without one), and under it
  always "更新於 3 小時前" with the overdue mark. Opened: below 900 px the facts of the bar, the body (folded, 顯示全部 in
  place), and for its own person "要求每 __ 小時更新" (set or clear), for others how often its person asks, dim. It
  starts open at 900 px and wider, closed below; the reader's choice is kept per project.
- **Two views**, a tab line drawn as the work page's tabs: **對話** and **動態**. My own agent opens in 對話, anybody
  else's in 動態, which is then its only view (the tab current, not a link), with one quiet line under the log: "只有
  {owner} 和 {owner} 的 agent 能私訊 {name}。要找它，在頻道裡提及 @{name}。" The 對話 tab carries the conversation's count
  only while the list is out of sight (below 900 px, or the left cells folded) and 動態 is shown.
- **對話** is the private page's own room (the same list, acts, unread line and read position, drafts, composer), not a
  copy: what was the private conversation with the agent. The composer's placeholder says what `@name` does there.
  Only seeing its end with the view in front reads a message; 動態 never does.
- **動態** is a log (see "A log entry"): newest first, in the reading column, nothing to write with. Its own line, not
  scrolling: the filter (**找它的和它說的**, the default: what it sent, what names it, its private conversations and
  its changes of state; or **全部**: also what it was handed in channels without being named; remembered) and, at the
  right, **全部展開** (pressed it reads 全部收合 and every row is open; not kept between visits). Day headings sticky
  at the top ("今天 · 11月23日 週一", "昨天 · …", else the date). Three or more entries alike in a row in one day (same
  direction and place, none important for the agent, none waiting) fold into one row ("在 #general 收到 4 則訊息 ·
  13:58–14:03") that opens to them. A row opens in place to the whole message (rendered as a message is), its reply
  line, 已編輯, the waiting line, and a foot with the time, the model and the link to where it is (a channel, "在對話開
  啟", or, between two agents of the reader's, the other agent's 動態). Older entries load at the foot (and by
  "載入更早的動態"); new ones come in at the top, and when the reader is scrolled down nothing moves and a plain pill
  "↑ 新動態" leads back up. Loading, empty, the beginning and "現在讀不到它的動態。" are said at the foot.
- With no agent at all, the column says so and the page is empty.

### The work page

- One page for the dashboard and the scheduled messages (`/{slug}/work`, `/work/schedules`; the former
  `/agent/tasks`, `/agent/schedules` and `/schedules` answer with the same page at the matching tab). Top left the
  project menu; top right the two tabs **儀表板 · 排程訊息**, drawn as the files tabs are (ink and a 2 px underline for
  the current one, no counts), and at the right one action for the current tab (new schedule), only for who may;
  below 900 px it is a round icon button with its name as label and tooltip.
- The second column lists the tab's scopes. The dashboard: **所有群組** (the first: every agent), then each group that
  has agents (the custom groups in their order, each person's agent group, then the default ones), with its number of
  agents. Schedules: all, mine, paused, each place. The scope is in the address's query, changed in place; below
  900 px the list is in the drawer and the content starts with one line naming the scope and its count, which opens
  it.
- **The dashboard** is one card per agent of the chosen scope, in a grid of cards on the surface: its avatar,
  presence, name (mono, 600, a link to the agent page), model tag and what it is doing; its person, "離線" when it is,
  and, for an agent of the reader's own, its quotas; then its status: the title (600), the body (about six lines,
  then "顯示全部" opens it in place), "更新於 3 小時前" with the overdue mark (an overdue card's edge is dashed too);
  "還沒有狀態" when it has none. For the agent's own person, "要求每 __ 小時更新" with 設定 and 不要求, saved in place;
  for others, "每 N 小時更新" as dim text.
- A schedule says where to, when next over how often, its text and its last message or why it is paused. Every row's
  acts are behind one "..." control; a new schedule is a form in place, which Escape closes.

### Files mode

- **Two sources, one explorer.** The top-left cell is the two sources side by side, two buttons:
  **公共** (the project's repository) and **私人** (a folder of the reader's own computer), the
  one shown pressed (`aria-pressed`). Both have the same tree, keyboard and entry menu. Above the tree, one line: the files menu
  (for the local source open folder, restore access when the browser must be asked again, and forget folder, two
  steps in place; for the repository **新增檔案** at the top for a reader who may save there, **重新整理** and the repository on
  GitHub) and the search field filling the rest. The opened
  local folder is one folder at the top of its tree, shown and handled like any folder (its name, folding, its entry
  menu); there is no separate bar with its name. With no folder open the local source is one control; a folder kept
  from an earlier visit is one control that restores access; in a browser that cannot open folders it is one sentence
  and no control. **Nothing of a local file reaches the server**: not its content, not its name, and a local tab has
  no address of its own.
- **Finding files**: typing in the search field shows, in the tree's place, the paths of the source shown that hold
  every word typed, the shortest first, each with its kind mark and the words marked as message search marks them
  (weight and a wash); the arrow keys and Enter open one (a folder in the
  tree); Escape or emptying the field gives the tree back. When the search could miss files (the repository was
  listed only in part, the folder has more than 20,000 entries) one quiet sentence says so.
- **The explorer chooses; the tab strip says what is open.** The strip is the top-right cell. One tab per open file,
  its name with the full path as its title; two tabs of the same name show after it, in dim ink, as much of their
  folder as tells them apart. **Each source keeps its own tabs** and its own current tab: the strip and the document
  are those of the source shown, and switching the source switches them (a file opened from the other source turns
  the source too). The strip scrolls sideways (the wheel too) and never wraps: a second row would make the order and
  the current tab hard to follow; an edge with more tabs beyond it fades out, only while there are. The current tab is
  lifted to the document's surface and underlined, not told by brightness alone.
- **Opening a file previews it in the current tab**, which it replaces, unless that tab holds unsaved edits: then the
  file opens in a new tab. A file opens in a new tab by the entry menu's "在新分頁開啟", a middle click, Ctrl/Cmd+click,
  or by dragging its row onto the strip, where a line marks the place it will go. A file already open has its tab
  chosen. Tabs are reordered by dragging them along the strip.
- At the strip's far right, and nothing else there: for a `.tex` file next to a PDF of the same name, the word
  "開啟 PDF" (it opens the PDF in a new tab); for a text file of the repository the word **編輯** (pressed while editing)
  when the reader may save there in their own GitHub name, with **儲存** beside it (an icon button, while the file is
  edited, disabled while nothing is unsaved; also Ctrl+S / Cmd+S; a local file has it in the same place), or in place
  of 編輯 a quiet link to the settings' 寫入公共檔案: "需要 GitHub 寫入授權" when saving needs their authorization, or
  "寫入電腦離線" / "寫入電腦無法寫入" / "寫入電腦不在這個專案" when the computer they chose to write is not connected,
  has no git or has not joined this project (nothing when their GitHub account cannot push); the view switch
  (rendered, source, both side by side) and "open on GitHub" for a file of the repository. Icon buttons with names and tooltips. A view that makes no sense for the file is disabled, not
  hidden, so the switch keeps its shape. There is no bar under the tabs: the address, the tab's title and the tree
  already say which file it is.
- **The source view is the editor, for both sources**: editable for a local text file; for the repository read only
  until **編輯**, which makes the same editor editable in place (a view showing only the rendering turns to the source).
  The mono voice with line numbers; prose (`.md`, `.tex`, `.txt`) wraps, code does not and scrolls sideways inside
  the editor. Its colours are the tokens, so it switches ends with the page. Beside it, the rendering of a Markdown
  file follows what is typed after a short pause, without taking the focus or moving its scroll.
- **Unsaved** is shape: a filled disc after the tab's name (and the word in its accessible name), never a colour.
  Closing that tab confirms in two steps; leaving the page asks through the browser's own question.
- **The repository is refreshed by hand.** Nothing asks GitHub by itself: 重新整理 in the files menu asks the server
  for the newest head now; the open folders are listed again and the open tabs read again when it moved, and the
  outcome ("已更新" / "已經是最新") is said for a moment over the tree. A local folder still follows the disk by itself.
- **What is shown is redrawn only when it changed.** A file read again (the disk moved, the repository has a new
  head) leaves the document alone when its bytes are the same; new text goes into the open editor and the rendering
  in place, keeping the scroll and the selection. A push to the repository never touches a local file shown.
- **A file is never overwritten silently.** A local file that is open and unchanged follows the disk by itself. With
  unsaved changes, saving first compares the disk with what was loaded; when they differ nothing is written, and one
  sentence over the document offers both ways, each in two steps: load the disk's version (the changes are lost) or
  write over it. A save that is refused says why in the same place.
- **Saving to the repository is a commit in the reader's own name.** Saving asks over the document, in place, for the
  commit message: one line, prefilled ("Edit {path} via Asterism"), with "存到 GitHub" and "取消"; while it goes, one dim
  line says so. When GitHub has another version nothing is written, and the same sentence offers "載入 GitHub 上的版本"
  or "用我的版本覆蓋", each in two steps. After a save the tab shows the new version, editing ends, and the tree and
  the other tabs follow as after 重新整理. A file of the repository with unsaved changes is never replaced by a push.
  Pressing the pressed **編輯** ends editing; with unsaved changes it says so first (two steps).
- **A new file of the repository** (its folder's menu, or the files menu for the top) asks for the name in the tree as
  a local one does, opens an empty tab being edited, and says over it that it reaches GitHub only when saved.
- **A file of the repository** has, for who may write there, **重新命名** (the name asked in the tree, in place, as for a
  local file) and **刪除** (floating, the name typed) in its entry menu; each is one commit in the reader's name. A
  rename onto a name GitHub already has, or of a file changed on GitHub since it was read, is refused under the field;
  a delete refused so says it in the panel; either way the tree is listed again. Its open tab follows a rename (and
  the address with it) and says the file is gone after a delete. Folders are not renamed or deleted as such.
- What cannot be shown or edited (too large, not text, not UTF-8) is one sentence where the document would be, with
  one link, or over the read-only editor.
- Below 900 px, while the source shown has no tab, the page is the explorer (the source, the search field and the
  tree), not an empty page; a file opened puts it back in the drawer.

## Interaction

- **One dropdown and one check box on every page.** There is no native `<select>`: a choice among several is a
  control with the current choice and a chevron that opens the choices as the one menu (each a choice of one, the
  current one marked by a filled ring and focused; arrow keys, a letter, Escape, the focus back on the control). Every
  check box and switch is the one check box: a 16 px box with a 4 px radius, filled with ink and carrying a tick in
  the page's ground when checked; a check item of a menu looks the same.
- **An act lives on the thing's row, and a refusal sits where the act would have been**, next to the control that was
  used, not in a banner. It is said in the page's own words, from the catalogue by the refusal's code (the act and
  the code, else the code alone), in the reader's language: never the server's sentence, which is English and written
  for agents. A field is checked in place: what is wrong with it is said under it (a name refused, a field left empty,
  an address that is not one), never in the browser's own bubble.
- What can be done to a message or a schedule appears on hover and on keyboard focus of its row; on a touch screen it is
  always there. Nothing is reachable by hover alone.
- **Right click is never the only way.** The menu of an entry (a file or folder in the explorer, a tab, a channel,
  a member's name, a group) opens by right click, by the context-menu key or Shift+F10 on the focused row, and by a
  control that does the same (the row's small control, the channel's gear and its settings, the member's card).
  It is one menu for the whole page: arrow keys move, Escape, Tab or a click outside close it, and the focus goes
  back where it was. The trees (the explorer, the member list) have the same keys: one tab stop, ↑ ↓ Home End and a
  letter move, → and ← open and close, Enter acts; a menu or a card opened from a row leaves the row's open state
  as it is. A choice among several (a member's groups) is a submenu of check boxes, marked by a filled
  box, not by hue. A list behind an item opens in its place with a way back, not as a second floating box.
- The outcome of a menu's act (copied, refreshed, a refusal) is said on the row it acted on, for a moment. A member's
  menu, whose list is drawn again by the reading that follows the act, says it in a small note under the row or the
  name it was opened from, and the next opening shows what the server holds. No refusal is dropped without a word: a
  card says it in the card (kept while the card is drawn again), and when the members cannot be read again after an
  act the page says so (the member list, the card, the agent page beside its "…", the settings of members and groups
  over the section).
- A name asked for (a new file or folder, a rename) is typed in the tree, in the row's place: Enter does it, Escape
  gives up, and a refused name is said under the field, which stays.
- **An act with a consequence confirms in place, in two steps**: the control changes to say what will happen
  ("確定移除這個排程") and a second press does it; moving away disarms it. No browser dialogs.
- **A destruction that cannot be undone floats**: a centred panel over a dimmed page, its button armed only when the
  thing's name is typed (a project's name, not its address; a channel's deletion asks without typing), and that
  button is the one red. A new project is made with its name (and repository); the server gives its address. Escape and a click
  outside close it.
- Focus is always visible. Motion is short (120–180 ms), only on what the reader just did, and off under
  `prefers-reduced-motion`.

## Copy

- Quiet, one sentence. Say what happens next, not what the system did inside.
- Interface text is Traditional Chinese or English, as the reader chose (else the browser's language), from the
  message catalogue, which holds both for every key. What agents read stays English and is not this file's business.
- The browser tab's icon is v1's mark (`static/favicon.svg`).
