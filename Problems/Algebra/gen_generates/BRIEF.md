# gen_generates — BRIEF

_Auto-rendered from `Manifest.md` + `Library/`. The framework_
_inlines this file into `Context.md` for every Builder /_
_Backward dispatch on this problem._

## Sandbox
- Reads allowed without permission prompts:
  - This goal's problem dir (your cwd).
  - `.lake/packages/mathlib/Mathlib/` for `rg`/`Read` on Mathlib source.
- Reads NOT allowed: other `Problems/<...>/` dirs — irrelevant to this goal. Use Loogle / Grep on Mathlib instead.
- `Context.md` + `PAST_*.md` companion files: read-only.
- `patch.lean` is your single output. Lead with `--` annotation comments, then edit the body (Builder fills in the proof; Backward edits the strategy skeleton's body — signature locked). See the kind-specific prompt for layout.

## Strategic notes (from Manifest.md)
`G n = Multiplicative (ZMod n)`, `gen n = Multiplicative.ofAdd (1 : ZMod n)`.

Goal: for any `x : G n`, exhibit `k : ℤ` such that `(gen n) ^ k = x`.

Translation through `Multiplicative`:
`(Multiplicative.ofAdd a) ^ k = Multiplicative.ofAdd (k • a)` (zsmul on the
additive side). So `(gen n)^k = x` ⟺ `k • (1 : ZMod n) = Multiplicative.toAdd x`.

In `ZMod n`, `k • (1 : ZMod n) = (k : ZMod n)` (integer cast). And every
element of `ZMod n` is the image of some integer cast (e.g. `Multiplicative.toAdd x`
itself reinterpreted as ℤ via `.val`). So a valid `k` is `((Multiplicative.toAdd x).val : ℤ)`.

Alternate route: Mathlib's `IsCyclic` instance for `ZMod n` might be available;
the multiplicative wrapping inherits it. If you can find `IsCyclic.exists_pow_eq`
or similar, the proof is one application.
