# Asterism — the visual language

The contract for EVERY user-facing surface: the web console (`web/`),
the installer pages (`installer/*.html`), whatever comes next. Read
this before writing or changing UI. Architecture and stack live in
`docs/internal/frontend_design.md`; this file is the visual language
only, and only the settled parts of it.

## Two ends of one scale (2026-08-07)

The language is achromatic and it now has a **light end**. Everything
below is written for the dark end and holds unchanged on the light
one, because both ladders invert together: the elevation ladder still
RISES toward the reader, and the ink ladder still runs loudest →
quietest. `star`/`starlight` are the sky's light in the dark and its
ink in the light; "the living carry the light" reads as "the living
carry the ink" with no component changed.

**No component may hardcode white or black.** Use the tokens —
`--color-wash{,-2,-3}` are the alpha plates (code blocks, diff rows,
meter tracks) and they carry the flip. A literal `bg-white/[0.02]` is
invisible on paper; that is how this rule was learned.

The choice is one attribute on `<html>` (`data-theme`), applied
before first paint by an inline script in `index.html`, stored in
localStorage, and defaulting to the system preference.

## Ink

- The chrome is **achromatic** — greys, black, white. No color
  anywhere without the owner's explicit per-instance sign-off.
- Encode with five axes instead of hue: **brightness, weight, shape,
  motion, inversion**.
- **Subtraction outranks addition.** The settled norm earns no ink;
  ink is for exceptions. Never draw the same fact twice.
- Identity and state are separate channels: identity = ring / shape /
  size; state = brightness / blink. Never mix the two axes in one
  mark (a legend swatch that carried both was a systemic bug source).

## The one sanctioned color: code

Lean — and only code — is colored, by the **single shared tokenizer**
`web/src/lib/lean.tsx` (six low-saturation inks; the file is the SoT
for the values). Every Lean fragment on every screen goes through it.
No rainbow brackets, no editor underlines: reading ink, not tooling
ink.

## Text blocks — one template (2026-08-27)

Every block of Lean, markdown or plain text is built by
`lib/textFrame` (`frameClass`, or the `TextFrame` component). Never
hand-write the chrome: that is how this rule became necessary.

- **Ground is `bg-wash`, always.** It is a 2% white overlay, so a block
  recedes from whatever is behind it. `bg-bg` and `bg-surface` are
  opaque — using them makes a block assume a host it may not have.
- **Radius is the container rung** (12px), like every other block that
  envelops content. Code blocks had all drifted onto the CONTROL rung.
- Only four things vary, and they are the language's own axes:
  `tone` (brightness), `size`, `lead` (`quote` = packed into a side
  panel, `read` = a thing you read), `cap` (reading room). Plus
  `frame: false` for a quotation already inside someone else's frame —
  two frames on one block draws the same fact twice.

Owner, 2026-08-27. Before it: 24 hand-written `<pre>` blocks across 14
files carrying four grounds, three paddings, five type sizes and four
ink levels for one object — and two verbatim copies of the editor
metrics string. A written law nothing owns is a law that drifts.

## Shape — the radius ladder

Radius states nesting depth: the more an element envelops, the
rounder it is (2026-07-18, owner push toward the modern end).

- **6px** (`rounded-md`) — micro: inline code chips, kbd, tags,
  row-hover highlights, mini inputs.
- **8px** (`rounded-lg`) — controls: buttons, selects, inputs,
  nav items.
- **12px** (`rounded-xl`) — containers: cards, panels, popovers,
  code blocks, editors, the floating destruction confirm.
- **16px** (`rounded-2xl`) — the chat composer pill.
- **full** — dots, pills, circular icon buttons, scrollbar thumbs.

Nested corners follow inner = outer − padding (a menu at 10px holds
6px option rows). The keyboard focus ring hugs each element's own
radius — never force one on the outline. Native select popups join
the ladder via `::picker(select)` where supported.

## Type — three voices

- **Inter** = the UI voice. **JetBrains Mono** = identifiers and code.
  **Fraunces** = the display voice (page titles, wordmark).
- Self-contained pages that cannot load fonts (installer) use the
  system stand-ins for the same three voices: Segoe UI / Consolas /
  Georgia.

## Glyphs — the sky's vocabulary, reused everywhere

- **Diamond = definition (data); circle = proposition.**
- **Single ring = a sign-off surface** (root / claim / anchor); bigger
  = more important. No other permanent rings.
- **A sign-off surface is one the READER signs.** v35 problems run
  several discussion groups, and a sub-group's `MarkDeliverable` is a
  brick handed to the group above it — machine bookkeeping, not a
  promise to the human. Read `human_facing_claim`, never
  `is_deliverable`, for anything that says "you vouch for this": on
  union_closed that was 1 of 24, and for a week the other 23 wore a
  ring saying otherwise (2026-08-13). They still draw, one size down
  and unringed, and the panel calls them *delivered* — the sky is
  always complete, so the fix is to mark them honestly, never to hide
  them.
- **A shell is a question closed with no light** (2026-08-26): refuted
  (disproved) or abandoned (dead). Everything still capable of coming
  home is a disc — proved (it did), live (it might), shelved and
  frozen (parked is not closed). One shell glows: a goal waiting on
  the strategist, where the light stopped and a decision is all that's
  missing. Hollow was tried for shelved the same day and the owner
  turned it down — *"shelved shouldn't go hollow, just make it
  darker."*
- **A brightness gap is a MEASURED distance, not a number that looked
  bigger in the diff** — the floor lives in `src/lib/sky.test.ts`,
  which resolves the palette out of `index.css` and composites each
  mark on the ground. Shelved and proved drifted together twice
  (45% → 55%, 2026-08-24) and the owner still read them as one dot at
  L\* 53.0 vs 33.8 — two same-size discs ~5px across beside a frontier
  at 96 that flattens everything under them. The room can only come
  from below, since proved may not brighten (ink inversion): shelved
  now sits at residue ink, L\* 23.8, 29.2 under the proved mass.
- **Solid = the machine's own decomposition; broken = a cross-link**
  (2026-08-26). Routes and anchor edges are solid; a citation dots, an
  alias dashes. `layout.ts` has always sorted them that way (hierarchy
  is walked, alias/citation are skipped) — until this date the ink did
  not say so, and since a route longer than 480 bows through the very
  same `citePath` a citation does, the only thing telling a
  decomposition from an import was an opacity that was simultaneously
  encoding density and span. Three facts, one channel, read as one
  tangle. Dotting also spends ~a third of a solid line's ink, so the
  weave runs ~1.6× the old weights: half the fog, twice the peak — one
  thread traceable where a hundred used to be a single wash.
- Routes (hierarchy lines, not alias/citation arcs) speak in **three
  voices** (2026-08-24): active = ink-dim, succeeded = starlight,
  everything else (dead/superseded) = ink-faint. Never paint a route
  with the rgba `--color-edge{,-strong}` tokens — their built-in alpha
  stacks under strokeOpacity and the line vanishes.
- State is brightness: while work is live the unproved stars carry the
  light and the proved mass recedes; a finished sky flips back to
  trophy. Writing-now = the star itself blinks.
- The console lane's expanded tail carries a **run a snapshot** action
  (2026-08-25): pressing it copies the tail as it stood into the
  reader's reserved Lean slot as an interactive probe — cursor shows
  the goal at any line, edits land in the copy and never in the
  agent's file, and the tail above keeps streaming while the agent
  writes. The copy re-wraps the goal's namespace (the tail arrives
  prelude-stripped); header `open` loss is repairable in the copy by
  adding the open.
- Refuted stars are **shells at residue weight** (2026-08-24): the
  question closed without light coming home, so a disproof never glows
  in any sky. Faint ink keeps the outline from masquerading as a
  sign-off ring (the ring is always the OUTER, concentric one).
- Frozen parks exactly like shelved: same disc, same ink, one legend
  row between them (2026-08-24).
- Shelved is **parked, not buried**: not a terminal state, so its trees
  stay readable — but the gap from proved comes out of ITS side, so
  "readable" is now a floor with a number on it (clearly above the
  abandoned residue, `sky.test.ts`), not a feeling. Dead alone is the
  very faint residue, and it is still never hidden. **The sky is
  always complete** — ink inversion is the only focus mechanism; no
  hide/filter toggles.
- **Settled things recede; they are never struck through.** The same
  law outside the sky (the Programme's discussion tree): a finished
  branch dims, a filled glyph says work came home and a hollow one
  says nothing did. `line-through` is spent — it means DELETED text
  in a diff, so striking a delivered thing would call its success a
  retraction (owner, 2026-08-07).

## Interaction

- Hover / selection = focus: related ink brightens, the rest recedes.
  Focus is shown by DIMMING what is not focused — never by lifting the
  focused thing into a popup. (This is a rule about focus, not a
  general verdict on floating surfaces; see below.)
- Actions with consequences confirm **in place, two-step** — the
  second click names what happens ("Confirm — engine runs now").
  Friction proportional to consequence.
- **Irreversible destruction MUST float.** Deleting a problem earns a
  floating confirm whose action button unlocks only when the thing's
  name is typed back, and that button is the achromatic law's single
  owner-sanctioned use of red (2026-07-09).
- A floating window is **not reserved to** that case (owner,
  2026-08-27, correcting this section: it had been written as "no
  modal dialogs except irreversible destruction", which turns a
  requirement into a monopoly — irreversible work must float; floating
  is not thereby limited to irreversible work). Float where a task is
  genuinely a task of its own: **browsing a collection to choose from
  it** is the standing example — the New page's paper picker floats
  because inlining the shelf buries the form it belongs to, and a
  bounded inline list makes the reader choose through a slot. Do not
  float what the page can simply say: a confirmation, a status, a
  field's own error.
- A floating surface follows the delete-confirm's shape: `fixed
  inset-0 z-50` over `bg-bg/70`, one centred `rounded-xl border
  border-edge bg-surface` panel, backdrop click and `Escape` both
  close it, focus lands inside it on open.
- Engine states speak inside the panel they affect, in plain words.
  The audience is mathematicians: human words in the UI, engine
  vocabulary in tooltips (`web/src/lib/vocab.ts` is the enum→word
  layer).
- Drop targets (Papers is the reference): the WHOLE route area
  accepts the drop; while a file is over it, a dashed `border-2
  border-ink-faint` frame at `inset-3 rounded-xl` floats over
  `bg-bg/85` with a two-line center label (display-face verb + quiet
  format list). No always-visible dropzone box — the affordance is a
  header hint sentence; the frame appears only mid-drag.

## Logs — a row names an object (2026-08-07)

Any surface that lists what the machine did reads
`when | what happened | to whom`, and the third field is a NAME the
reader can act on — a goal slug, the Programme, a group, a paper.

- **Prose is never a headline.** An agent brief is over a kilobyte of
  markdown; as a row's summary it truncates to boilerplate and buries
  the one token that identifies the event. Briefs live in the
  expansion.
- **Because every row names an object, the log can be followed by
  object** — the name click opens that star on the map (the side
  panel carries the history; the run view walks to the problem's own
  page), and the row's expansion offers *follow through the log* for
  the single object's whole life. A row that names nothing breaks the
  shape and does not render at all: mint requests for bricks that
  don't exist yet are dropped, not queued behind a "quiet" toggle
  (2026-08-24). Dispatch starts ("asked for") live in the follow view
  only — in the stream they double every attempt whose outcome already
  has a row (2026-08-25).
- **Outcomes are events too.** A log of what was *decided* without
  what *became of it* answers none of the questions a reader arrives
  with (`Timeline` showed 0 of 52 landings before this rule).
- **A reconstructed timestamp says so.** Where a time is inferred
  rather than recorded, mark the row (`~`) and draw the boundary where
  the real record begins — otherwise nobody can tell later which half
  was true.

## Copy

- Quiet, lowercase-leaning, one sentence. Say what happens next, not
  what the system did internally. UI text is English.
