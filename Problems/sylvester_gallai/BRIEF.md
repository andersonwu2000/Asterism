# sylvester_gallai — BRIEF

_Auto-rendered from `Manifest.md` + `Library/`. The framework_
_inlines this file into `Context.md` for every Builder /_
_Backward dispatch on this problem._

## Sandbox
- Reads allowed without permission prompts:
  - This goal's problem dir (your cwd).
  - `.lake/packages/mathlib/Mathlib/` for `rg`/`Read` on Mathlib source.
- Reads NOT allowed: other `Problems/<...>/` dirs — irrelevant to this goal. Use Loogle / Grep on Mathlib instead.
- `Context.md` + `PAST_*.md` companion files: read-only.
- `patch.lean` is your single output. Lead with `--` annotation comments, then edit the body (Builder fills in the proof; Backward edits the F52 skeleton's body — signature locked). See the kind-specific prompt for layout.

## Strategic notes (from Manifest.md)
Sylvester–Gallai theorem. Freek-100; known proven, NOT in Mathlib.

The custom `Collinear p q r` is the determinant test
`(p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)` (see `Defs.lean`),
not Mathlib's `AffineSubspace`-based predicate.

Kelly's proof (1948):
- Consider pairs (line ℓ through ≥2 points of P, point p ∈ P off ℓ).
- Minimise the perpendicular distance from p to ℓ; pick minimiser (ℓ*, p*).
- Suppose ℓ* contains ≥3 points. The foot of perpendicular from p*
  has at least two of them on one side; the closer of those two with
  p* defines a line strictly closer to the third. Contradiction.
- Hence ℓ* has exactly 2 points of P.
