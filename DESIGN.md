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
- Two exceptions, and only these:
  - **Code and mathematics** keep whatever colour their renderer gives them. Code is the one sanctioned use of
    hue: the editor's highlighting colours keywords, declared names, types, strings, numbers and attributes with
    the six muted `--color-syn-*` tokens (defined for both ends like every token); comments are `--color-ink-dim`.
  - **One red**, `--color-destruct`, for the armed button of a destruction that cannot be undone. Nothing else is red:
    not errors, not warnings, not "remove" before it is armed.

## Two ends of one scale

There is a dark end and a light end, and every rule here holds on both, because both ladders invert together: the
surfaces still rise toward the reader, the ink still runs loudest to quietest.

- The choice is one attribute on `<html>`, `data-theme="dark"` or `"light"`, set before first paint, kept in
  localStorage, defaulting to the system preference. The reader can switch it from the navigation.
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
| `--color-ink-faint` | `#67696f` | `#85878e` | marks and rules only: too quiet for a sentence |
| `--color-loud` | `#f4f5f8` | `#101014` | what asks for the reader: the ground of an inverted pill |
| `--color-destruct` | `#a33a35` | `#a33a35` | the one red |
| `--color-syn-keyword` | `#de8e9f` | `#a33e52` | code: keywords, TeX commands |
| `--color-syn-name` | `#8ab6dd` | `#2f6392` | code: declared names |
| `--color-syn-type` | `#82c0ae` | `#1f7a63` | code: types and sorts, TeX environments |
| `--color-syn-string` | `#a6c18b` | `#4c7333` | code: strings, TeX labels and citations |
| `--color-syn-number` | `#d5ac7c` | `#8a5b1f` | code: numbers |
| `--color-syn-attr` | `#b3a0cf` | `#6a4fa3` | code: attributes, TeX math delimiters |

Depth is stepped surface lightness, never a shadow.

## What the marks mean

- **Important** (a message that needs the reader, and a count of such messages) is an **inverted pill**:
  `--color-loud` ground, `--color-bg` text. It is the loudest thing on a page; a page with three of them has stopped
  saying anything. A control that is armed for its second press wears the same inversion while it is armed.
- **Locked** (a task a person assigned) is a quiet tag: `--color-edge-strong` outline, `--color-ink-dim` text, saying
  who assigned it. A lock is a settled fact, not a call for attention.
- **A task is held by an agent or by nobody**, never by a person. On the agent page's task tab a task shows its number
  (mono, 12 px, dim: agents and the system's notices name tasks by number); a message still shows none.
- **A schedule's level** is a quiet tag; the usual level (normal) is unmarked.
- **Unread** is weight: the name of a place with unread messages is in `--color-ink` at weight 600; a place with none
  is `--color-ink-dim` at 400. The count is plain dim text.
- **Muted** recedes: `--color-ink-dim` at weight 400 and no unread count, with the word for muted beside the name.
  What is important for the reader still shows its inverted pill there: muting a place silences its talk, not a
  message that names the reader.
- **Who is there** is shape and fill, 10 px: shape says who, fill says state.
  - an agent: a disc; a person: a square with a 2 px radius;
  - online: filled in `--color-ink`; offline: hollow, its outline in `--color-ink-faint`. A person is online while a
    page of the project is open in a browser (the page beats every few seconds); an agent as its presence says.
- **Busy** is a word next to the name, not a colour.
- **The current place** in the navigation is `--color-wash-3` under `--color-ink`.
- **The kind of a file** is v1's kind mark (a folder, prose lines for Markdown, the same lines centred for TeX, a
  chevron for Lean, a folded corner for a PDF, a landscape frame for a picture, a blank page for anything else), on a
  10×11 box in the current ink, before the name in the explorer's rows and the tabs. Decorative: the name says it.
- A message shows **no number**: its id stays in the page's data, for replies and jumps.
- **A count in a list of scopes** (the agent page's second column) is plain dim text, absent when 0; weight is never
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
- Body 14 px on a 1.5 line; secondary 13 px; the smallest text is 12 px and it is never a sentence.
- Text against its ground is at least 4.5:1. `--color-ink-faint` does not reach that: it is for marks.

## Layout

- **Every page of a project has the same four cells** beside the **rail** (a fixed narrow column on the far left):
  the **top-left cell**, one line over the second column, on its surface; the **second column** under it; the
  **top-right cell**, one line over the page (the page's title or tabs at its left, its actions at its right); and
  the **page** under it. The lines between the cells are the same everywhere: the second column's divider runs up
  through the top line, and the top line's rule runs under both top cells. Chat, private messages, files, the agent
  page and the settings layer all have them.
- The rail holds the top-level buttons, each a line glyph (`currentColor`, decorative) with a short word under it:
  chat, private messages, files, agent. No divider between them. At its foot the theme switch and the reader
  (sign-out is reached from there). The current one is the current place; hover washes the glyph's tile only, so the
  word never jumps. Members, groups and the project's settings are not on the rail: the project menu leads there.
- **Folding**: in a mode (chat, private messages, files, agent), pressing the button of the mode one is already in
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
  Files mode has no project name and no project menu.
- **Settings are one layer in the four cells** (the rail stays): the project's settings (overview; people: members,
  groups, invitations) and one channel's (overview, notifications) look the same. Top left the project's name and
  what is set ("設定", or the channel's), the list of sections under small headings in the second column, top right
  the section's title and a round close control with "Esc" beside it; Escape closes, back to the page it was opened
  from, else chat. Each section has its own address; the bare address is the first section.
- **Groups (群組) as Discord orders roles.** The groups in their order, the highest first, each with its member count;
  who may manage groups drags a row to move it (a grip marks the row; a line shows where it will go) or uses "move up"
  / "move down" in the row's menu, so the order is reachable by keyboard. Under them the three default groups, written
  by their names, **owner**, **human**, **AI**, each a row of its own marked "預設" in quiet ink, not draggable,
  opening on its own: its permissions (fixed) and its members. A chosen group shows the list as a middle column and
  the group in tabs: display (its name and the switch "在成員列表中分開顯示"), permissions, members; a person's agents:
  display, members and that person's switches. Default groups are never shown as groups anywhere else: a member's
  chips list only the other groups; in the members section of settings the default ones are a quiet line
  ("預設：owner・human"), and the + there offers every group, the default ones too, as check boxes.
- Chat, private messages, files and agent are **modes**; the settings layer is not. Outside chat, the chat button
  carries the count of channel messages important for the reader as the inverted pill, and outside private messages
  the private-messages button the same for private conversations; in its own mode a button carries nothing, the
  second column says it.
- The second column belongs to the mode: in chat the channels; in private messages the conversations (newest first,
  with their unread marks, and a + that offers, as a menu, the members one may write to privately); in files the
  explorer; on the agent page the current tab's **list of scopes**; in settings the sections. A list of scopes looks
  like chat's places: short rows under small headings, the chosen one the current place, the others dim, a count as
  plain dim text.
- Each mode remembers its place: the chat button returns to the place last open, files reopens its tabs, the agent
  button returns to the tab and scope last shown.
- **Files use the whole page.** Browsing, reading and editing files never sit beside the chat; the rail switches
  between them.
- Prose is held to a **reading column** of at most 880 px, centred in its area. Wide content (tables, code, display
  formulas, pictures, a PDF) may use the whole area; the message list uses the room it has.
- A channel's row in the second column shows a sliders mark for its settings on hover and focus. The page shows no
  pins.
- **The right column shows one thing at a time**, or nothing: the member list, or search. Their buttons in the top
  bar show or hide them; whether the member list is open is remembered per project. Search takes the column while it
  is open: its field at the top (in a channel limited to it at first, shown as a removable chip), the results under
  it (newest first, the words marked by weight and a wash, never by hue); Escape on an empty field or its × gives the
  column back.
- **The member list** has a switch at its top, people | agents (remembered). Sections as Discord's: one per group
  shown separately, in the groups' order, holding the online members whose highest such group it is; then "在線"
  for the other online members; then "離線" for every offline member, whatever their groups. Under an agent's name,
  its tasks as its status (a person holds none): a task's text on one line, cut with an ellipsis; more than one task,
  or a long one, folds under "n 項任務", opened in place; a locked task carries the quiet tag. On the agents' side,
  first, the tasks nobody holds, folded, with "open in the task table" and "new task" (its group chosen). A member's
  row has its menu (a "..." control, right click, the context-menu key or Shift+F10); an agent's has "new task" and
  "open in the task table"; each task has its own small menu: edit (in place), hand to another agent ..., lock or
  unlock, release, remove (in two steps, in place), offered only where the page cannot already tell the answer is no.
  It is the agent page's task menu too.
- **A profile card** is a small popover by the name it was opened from (in a message, the member list): name, kind,
  presence, groups as chips (× and + for who may change them; never the default groups), an agent's tasks, and the
  acts mention, private message (only where the server allows it) and open in settings. Escape closes it; the focus
  goes back to the name.
- **Private messages** have a page of their own (`/{slug}/dm/{name}`; the bare address opens the newest
  conversation): the conversation in the middle with the same composer and top bar as chat. An older address of a
  private conversation in chat leads there.
- Below 900 px the rail and the left cells live together in a drawer opened from the start of the top-right cell: the
  top-left cell (the project's name with its menu, the source in files, the project's name in settings) is the head
  of the second column there. The right column is a sheet over the messages that starts closed. Nothing scrolls
  sideways at 360 px.
- Lists that update (messages, tasks, schedules, the explorer) never move what the reader is looking at: new things
  arrive at the end, and an editor that is open survives a refresh.

### The agent page

- One page for my agents, the task table and the scheduled messages (`/{slug}/agent`, `/agent/tasks`,
  `/agent/schedules`; the former `/my` and `/schedules` answer with the same page at the matching tab). Top left the
  project menu; top right the three tabs **agent · 任務 · 排程訊息**, drawn as the files tabs are (ink and a 2 px
  underline for the current one, no counts), and at the right one action for the current tab (invite agent / new
  task / new schedule), only for who may; below 900 px it is a round icon button with its name as label and tooltip.
- The second column lists the tab's scopes (mine and each other person's agents; all, my agents', assigned by me,
  nobody's, each group; all, mine, paused, each place). The scope is in the address's query, changed in place; below
  900 px the list is in the drawer and the content starts with one line naming the scope and its count, which opens
  it.
- The content is one list in the reading column. An agent is a block: presence, name, kind; where it is, its last
  activity and its tasks as a link; an offline agent's reason on a wash (offline is the exception, online is said by
  the disc alone); its groups as chips, the default ones as a quiet line. Computers and connectors say which agents
  are on them; revoking floats. My switches save as they change. Tasks are grouped by group, then by agent, with
  their numbers and whole texts (four lines, then "顯示全部"). A schedule says where to, when next over how often, its
  text and its last message or why it is paused. Every row's acts are behind one "..." control; a new task or
  schedule is a form in place, which Escape closes.

### Files mode

- **Two sources, one explorer.** The top-left cell is the source shown as a dropdown, as chat's project name:
  "公共 ▾" (the project's repository) or "私人 ▾" (a folder of the reader's own computer), opening a menu of the two,
  the current one checked. Both have the same tree, keyboard and entry menu. Above the tree, one line: the files menu
  (for the local source open folder, restore access when the browser must be asked again, and forget folder, two
  steps in place; for the repository, the repository on GitHub) and the search field filling the rest. The opened
  local folder is one folder at the top of its tree, shown and handled like any folder (its name, folding, its entry
  menu); there is no separate bar with its name. With no folder open the local source is one control; a folder kept
  from an earlier visit is one control that restores access; in a browser that cannot open folders it is one sentence
  and no control. **Nothing of a local file reaches the server**: not its content, not its name, and a local tab has
  no address of its own.
- **Finding files**: typing in the search field shows, in the tree's place, the paths of the source shown that hold
  every word typed, the shortest first, each with its kind mark; the arrow keys and Enter open one (a folder in the
  tree); Escape or emptying the field gives the tree back. When the search could miss files (the repository was
  listed only in part, the folder has more than 20,000 entries) one quiet sentence says so.
- **The explorer chooses; the tab strip says what is open.** The strip is the top-right cell. One tab per open file,
  its name with the full path as its title; tabs are per source, and a local tab carries a small mark before its
  name. The strip scrolls sideways and never wraps: a second row would make the order and the current tab hard to
  follow. The current tab is lifted to the document's surface and underlined, not told by brightness alone.
- **Opening a file previews it in the current tab**, which it replaces, unless that tab holds unsaved edits: then the
  file opens in a new tab. A file opens in a new tab by the entry menu's "在新分頁開啟", a middle click, Ctrl/Cmd+click,
  or by dragging its row onto the strip, where a line marks the place it will go. A file already open has its tab
  chosen. Tabs are reordered by dragging them along the strip.
- At the strip's far right, and nothing else there: the view switch (rendered, source, both side by side) and one
  more control in the same place: "open on GitHub" for a file of the repository, **save** for a local file (also
  Ctrl+S / Cmd+S). Icon buttons with names and tooltips. A view that makes no sense for the file is disabled, not
  hidden, so the switch keeps its shape. There is no bar under the tabs: the address, the tab's title and the tree
  already say which file it is.
- **The source view is the editor, for both sources**: read only for the repository, editable for a local text file.
  The mono voice with line numbers; prose (`.md`, `.tex`, `.txt`) wraps, code does not and scrolls sideways inside
  the editor. Its colours are the tokens, so it switches ends with the page. Beside it, the rendering of a Markdown
  file follows what is typed after a short pause, without taking the focus or moving its scroll.
- **Unsaved** is shape: a filled disc after the tab's name (and the word in its accessible name), never a colour.
  Closing that tab confirms in two steps; leaving the page asks through the browser's own question.
- **What is shown is redrawn only when it changed.** A file read again (the disk moved, the repository has a new
  head) leaves the document alone when its bytes are the same; new text goes into the open editor and the rendering
  in place, keeping the scroll and the selection. A push to the repository never touches a local file shown.
- **A file is never overwritten silently.** A local file that is open and unchanged follows the disk by itself. With
  unsaved changes, saving first compares the disk with what was loaded; when they differ nothing is written, and one
  sentence over the document offers both ways, each in two steps: load the disk's version (the changes are lost) or
  write over it. A save that is refused says why in the same place.
- What cannot be shown or edited (too large, not text, not UTF-8) is one sentence where the document would be, with
  one link, or over the read-only editor.

## Interaction

- **One dropdown and one check box on every page.** There is no native `<select>`: a choice among several is a
  control with the current choice and a chevron that opens the choices as the one menu (each a choice of one, the
  current one marked by a filled ring and focused; arrow keys, a letter, Escape, the focus back on the control). Every
  check box and switch is the one check box: a 16 px box with a 4 px radius, filled with ink and carrying a tick in
  the page's ground when checked; a check item of a menu looks the same.
- **An act lives on the thing's row, and a refusal sits where the act would have been.** The server's sentence is
  shown next to the control that was used, not in a banner.
- What can be done to a message or a task appears on hover and on keyboard focus of its row; on a touch screen it is
  always there. Nothing is reachable by hover alone.
- **Right click is never the only way.** The menu of an entry (a file or folder in the explorer, a tab, a channel,
  a member's name, a group) opens by right click, by the context-menu key or Shift+F10 on the focused row, and by a
  control that does the same (the row's small control, the channel's gear and its settings, the member's card).
  It is one menu for the whole page: arrow keys move, Escape, Tab or a click outside close it, and the focus goes
  back where it was. A choice among several (a member's groups) is a submenu of check boxes, marked by a filled
  box, not by hue. A list behind an item (the channels to pin to) opens in
  its place with a way back, not as a second floating box.
- The outcome of a menu's act (copied, pinned, the server's refusal) is said on the row it acted on, for a moment.
- A name asked for (a new file or folder, a rename) is typed in the tree, in the row's place: Enter does it, Escape
  gives up, and a refused name is said under the field, which stays.
- **An act with a consequence confirms in place, in two steps**: the control changes to say what will happen
  ("移除任務 12") and a second press does it; moving away disarms it. No browser dialogs.
- **A destruction that cannot be undone floats**: a centred panel over a dimmed page, its button armed only when the
  thing's name is typed, and that button is the one red. Escape and a click outside close it.
- Focus is always visible. Motion is short (120–180 ms), only on what the reader just did, and off under
  `prefers-reduced-motion`.

## Copy

- Quiet, one sentence. Say what happens next, not what the system did inside.
- Interface text is Traditional Chinese, from the message catalogue. What agents read stays English and is not this
  file's business.
