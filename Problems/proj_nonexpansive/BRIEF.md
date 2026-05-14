# proj_nonexpansive — BRIEF

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
The classical Hilbert-space argument has three layers, each a natural sub-goal:

1. **Variational inequality** for the metric projector. From the minimisation
   property `‖x − P x‖ ≤ ‖x − y‖` for `y ∈ K`, derive
   `Real.inner (P x − x) (y − P x) ≥ 0` for every `y ∈ K`. Standard trick:
   substitute `y := (1−t)·(P x) + t·y` for small `t > 0`, expand `‖x − …‖²`,
   divide by `t`, take `t → 0⁺`. The convexity of `K` is needed exactly here.

2. **Apply variational at both x and y** with the OTHER projection as the
   test point: take `y = P (something else)`. Adding the two inequalities
   yields `‖P x − P y‖² ≤ Real.inner (x − y) (P x − P y)`.

3. **Cauchy-Schwarz + cancellation**. By Cauchy-Schwarz the right side is
   `≤ ‖x − y‖ · ‖P x − P y‖`. Divide both sides by `‖P x − P y‖`
   (handle the degenerate case `P x = P y` separately).

`P` is given as a hypothesis — no need to construct it. Don't reach for
`Submodule.orthogonalProjection`; that's for closed *subspaces* and gives
linearity which we don't have here. The work is purely the three-step
inner product manipulation above.
