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
  - **Code and mathematics** keep whatever colour their renderer gives them.
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

- Every page of a project has the same frame: the **navigation** on the left (the project, its channels, private
  conversations, then the other pages, then the reader), the page in the middle, and on the messages page the
  **task table** on the right, which the reader can fold away.
- The middle column of a reading page is at most 880 px wide; the message list uses the room it has.
- Below 900 px the navigation becomes a drawer opened from the page's header, and the task table opens over the
  messages instead of beside them. Nothing scrolls sideways at 360 px.
- Lists that update (messages, tasks, schedules) never move what the reader is looking at: new things arrive at the
  end, and an editor that is open survives a refresh.

## Interaction

- **An act lives on the thing's row, and a refusal sits where the act would have been.** The server's sentence is
  shown next to the control that was used, not in a banner.
- What can be done to a message or a task appears on hover and on keyboard focus of its row; on a touch screen it is
  always there. Nothing is reachable by hover alone.
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
