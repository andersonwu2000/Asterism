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
- State is brightness: while work is live the unproved stars carry the
  light and the proved mass recedes; a finished sky flips back to
  trophy. Writing-now = the star itself blinks.
- Dead/shelved = very faint residue, never hidden. **The sky is always
  complete** — ink inversion is the only focus mechanism; no hide/
  filter toggles.
- **Settled things recede; they are never struck through.** The same
  law outside the sky (the Programme's discussion tree): a finished
  branch dims, a filled glyph says work came home and a hollow one
  says nothing did. `line-through` is spent — it means DELETED text
  in a diff, so striking a delivered thing would call its success a
  retraction (owner, 2026-08-07).

## Interaction

- Hover / selection = focus: related ink brightens, the rest recedes.
  Prefer dimming over popups.
- Actions with consequences confirm **in place, two-step** — the
  second click names what happens ("Confirm — engine runs now"). No
  modal dialogs — with ONE exception: **irreversible destruction**
  (deleting a problem) earns a floating confirm whose action button
  unlocks only when the thing's name is typed back, and that button
  is the achromatic law's single owner-sanctioned use of red
  (2026-07-09). Friction proportional to consequence.
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

## Copy

- Quiet, lowercase-leaning, one sentence. Say what happens next, not
  what the system did internally. UI text is English.
