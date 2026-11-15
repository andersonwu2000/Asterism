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
    hue: the source view's tokenizers colour keywords, declared names, types, strings, numbers and attributes with
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
  chat, files, scheduled messages, members and groups, my agents, project settings (only for who may). No divider
  between them. At its foot the theme switch and the reader (sign-out is reached from there). The current one is
  the current place; hover washes the glyph's tile only, so the word never jumps.
- Chat and files are **modes**; the other pages are just pages. Outside chat, the chat button carries the count of
  messages important for the reader as the inverted pill; in chat it carries nothing, the second column says it.
- The second column belongs to the mode: in chat the project, its channels and private conversations; in files the
  explorer; on the other pages there is none. A button at the start of the page's header folds it away on a wide
  screen, remembered per mode, applied before the first paint. The control lives outside the column, so it is
  always reachable.
- Each mode remembers its place: the chat button returns to the place last open, files reopens its tabs.
- **Files use the whole page.** Browsing, reading and (later) editing files never sit beside the chat; the rail
  switches between them.
- Prose is held to a **reading column** of at most 880 px, centred in its area. Wide content (tables, code, display
  formulas, pictures, a PDF) may use the whole area; the message list uses the room it has.
- On the messages page the **task table** sits on the right and can be folded away.
- Below 900 px the rail and the mode's second column live together in a drawer opened from the page's header; the
  fold buttons are gone there, and the task table opens over the messages. Nothing scrolls sideways at 360 px.
- Lists that update (messages, tasks, schedules, the explorer) never move what the reader is looking at: new things
  arrive at the end, and an editor that is open survives a refresh.

### Files mode

- **The explorer chooses; the tab strip says what is open.** One tab per open file, its name with the full path as
  its title. The strip scrolls sideways and never wraps: a second row would make the order and the current tab hard
  to follow. The current tab is lifted to the document's surface and underlined, not told by brightness alone.
- At the strip's far right, and nothing else there: the view switch (rendered, source, both side by side) and "open
  on GitHub", as icon buttons with names and tooltips. A view that makes no sense for the file is disabled, not
  hidden, so the switch keeps its shape. There is no bar under the tabs: the address, the tab's title and the tree
  already say which file it is.
- Source is in the mono voice with line numbers, not wrapped; a long line scrolls inside its block.
- What the server cannot show (too large, not text) is one sentence and one link, where the document would be.

## Interaction

- **An act lives on the thing's row, and a refusal sits where the act would have been.** The server's sentence is
  shown next to the control that was used, not in a banner.
- What can be done to a message or a task appears on hover and on keyboard focus of its row; on a touch screen it is
  always there. Nothing is reachable by hover alone.
- **Right click is never the only way.** The menu of an entry (a file or folder in the explorer, a tab) opens by right
  click, by the context-menu key or Shift+F10 on the focused row, and by a small control on the row (on hover and
  focus; always on a touch screen). It is one menu for the whole page: arrow keys move, Escape, Tab or a click
  outside close it, and the focus goes back where it was. A list behind an item (the channels to pin to) opens in
  its place with a way back, not as a second floating box.
- The outcome of a menu's act (copied, pinned, the server's refusal) is said on the row it acted on, for a moment.
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
