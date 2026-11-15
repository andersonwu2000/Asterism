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
- **Unread** is weight: the name of a place with unread messages is in `--color-ink` at weight 600; a place with none
  is `--color-ink-dim` at 400. The count is plain dim text.
- **Muted** recedes: `--color-ink-dim` at weight 400 and no unread count, with the word for muted beside the name.
  What is important for the reader still shows its inverted pill there: muting a place silences its talk, not a
  message that names the reader.
- **Who is there** is shape and fill, 10 px:
  - an agent that is online: a filled disc in `--color-ink`;
  - an agent that is offline: a ring in `--color-ink-faint`, hollow;
  - a person: a filled square with a 2 px radius in `--color-ink-dim` (people have no presence yet).
- **Busy** is a word next to the name, not a colour.
- **The current place** in the navigation is `--color-wash-3` under `--color-ink`.
- **Settled things recede; they are never struck through.**

## Shape — the radius ladder

Radius states nesting depth: the more an element envelops, the rounder it is.

- **6 px** — micro: tags, inline code, a row's hover highlight.
- **8 px** — controls: buttons, inputs, selects, navigation rows.
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

- Every page of a project has the same frame: the **rail**, a fixed narrow column on the far left, then the mode's
  **second column**, then the page.
- The rail holds the top-level buttons, each a line glyph (`currentColor`, decorative) with a short word under it:
  chat, files, scheduled messages, my agents. No divider between them. At its foot the theme switch and the reader
  (sign-out is reached from there). The current one is the current place; hover washes the glyph's tile only, so
  the word never jumps. Members, groups and the project's settings are not on the rail: the project menu leads there.
- **The project menu.** The project's name on top of the second column (both modes) is a button with a chevron; it
  opens the project's menu under it: invite people, invite an agent of mine, project settings, create channel, my
  agents, each only for who may use it. Beside the name, an icon for inviting people (for who may). What these acts
  ask for (a login, a channel's name) is asked in one floating panel over the dimmed page, which Escape and a click
  outside close; the answer (a link with its copy control) shows in that panel.
- **Settings are one full-page layer** over the frame (the rail stays): the project's settings (overview; people:
  members, groups, invitations) and one channel's (overview, notifications, pins) look the same. A list of sections
  under small headings on the left, the section on the right, and at the top right a round close control with
  "Esc" under it; Escape closes, back to the page it was opened from, else chat. Each section has its own address.
  Groups are a list with a filter and "new group"; a chosen group shows the list as a middle column and the group in
  tabs (name, permissions, members). Below 900 px the layer is the whole screen and its list of sections is a page
  of its own, each section with a way back to it.
- Chat and files are **modes**; the other pages are just pages. Outside chat, the chat button carries the count of
  messages important for the reader as the inverted pill; in chat it carries nothing, the second column says it.
- The second column belongs to the mode: in chat the project, its channels and private conversations; in files the
  explorer; on the other pages there is none. A button at the start of the page's header folds it away on a wide
  screen, remembered per mode, applied before the first paint. The control lives outside the column, so it is
  always reachable.
- Each mode remembers its place: the chat button returns to the place last open, files reopens its tabs.
- **Files use the whole page.** Browsing, reading and editing files never sit beside the chat; the rail switches
  between them.
- Prose is held to a **reading column** of at most 880 px, centred in its area. Wide content (tables, code, display
  formulas, pictures, a PDF) may use the whole area; the message list uses the room it has.
- **The channel bar** (the messages page's header): the button that folds the second column at the far left; the
  place's name as a button (a channel's opens its settings, a private conversation's the other member's profile
  card); then, at the right, icon buttons with names and tooltips in a fixed order: pins (with their count; they
  open in a popover), task table, member list; then the search field at the far right. In a channel the search
  starts limited to it, shown as a removable chip in the field. A channel's row in the second column shows a gear
  for its settings on hover and focus.
- **The right column shows one thing at a time**, or nothing: the task table, the member list (people, then agents
  online and offline), or search results (newest first, the words marked by weight and a wash, never by hue). Its
  buttons in the channel bar show or hide their panel; which one is open is remembered per project. Search results
  take it while a search is shown and give back what was there.
- **A profile card** is a small popover by the name it was opened from (in a message, the member list, the task
  table): name, kind, presence, groups as chips (× and + for who may change them), an agent's tasks, and the acts
  mention, private message (only where the server allows it) and open in settings. Escape closes it; the focus goes
  back to the name.
- Below 900 px the rail and the mode's second column live together in a drawer opened from the page's header; the
  fold buttons are gone there, and the right column is a sheet over the messages that starts closed. Nothing
  scrolls sideways at 360 px.
- Lists that update (messages, tasks, schedules, the explorer) never move what the reader is looking at: new things
  arrive at the end, and an editor that is open survives a refresh.

### Files mode

- **Two sources, one explorer.** A switch at the top of the explorer chooses between the project's repository and a
  folder of the reader's own computer. Both have the same tree, filter, keyboard and entry menu. With no folder open
  the local source is one control; a folder kept from an earlier visit is one control that restores access; in a
  browser that cannot open folders it is one sentence and no control. **Nothing of a local file reaches the server**:
  not its content, not its name, and a local tab has no address of its own.
- **The explorer chooses; the tab strip says what is open.** One tab per open file, its name with the full path as
  its title; tabs are per source, and a local tab carries a small mark before its name. The strip scrolls sideways
  and never wraps: a second row would make the order and the current tab hard to follow. The current tab is lifted
  to the document's surface and underlined, not told by brightness alone.
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
- **A file is never overwritten silently.** A local file that is open and unchanged follows the disk by itself. With
  unsaved changes, saving first compares the disk with what was loaded; when they differ nothing is written, and one
  sentence over the document offers both ways, each in two steps: load the disk's version (the changes are lost) or
  write over it. A save that is refused says why in the same place.
- What cannot be shown or edited (too large, not text, not UTF-8) is one sentence where the document would be, with
  one link, or over the read-only editor.

## Interaction

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
