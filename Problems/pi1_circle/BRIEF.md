# pi1_circle — BRIEF

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
Algebraic-topology route (operator preference; matches the standard
undergraduate proof). Use Mathlib's existing covering-map machinery —
do NOT rebuild `IsCoveringMap Circle.exp`, do NOT redefine `Circle.exp`,
do NOT build a new `liftPath`.

Standard assembly:
- For a loop `γ : Path (1:Circle) 1`, lift via
  `Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0 (by simp)`
  to a path in `ℝ` starting at 0.
- The lifted endpoint `Γ(1) : ℝ` satisfies `Circle.exp (Γ 1) = 1`, so
  by `Circle.exp_eq_one` it lies in `2π · ℤ` — define `winding γ : ℤ`
  via `Classical.choose` on that existential, with characterizing
  equation `(Γ 1 : ℝ) = winding γ * (2 * π)`.
- Homotopy invariance: `IsCoveringMap.monodromy` already packages the
  lifted endpoint as a function on `Path.Homotopic.Quotient`, so
  `winding` descends to `FundamentalGroup Circle 1` without re-deriving
  homotopy lifting from scratch.
- Group-hom: `monodromy_refl` gives `winding 1 = 0`;
  `monodromy_trans_apply` gives `winding (a * b) = winding a + winding b`.
- Bijection: `monodromy_bijective` + the standard-loop construction
  `γ_n : Path (1:Circle) 1` with `winding γ_n = n` (e.g. via
  `Circle.exp ∘ (·  * n * (2 * π))` traced over `[0, 1]`).
- Assemble: `MulEquiv` from `FundamentalGroup Circle 1` to
  `Multiplicative ℤ` via `winding` + its inverse.

Do NOT use winding-number formulations (`Complex.windingNumber`,
`exp_winding_integral_eq_one`, `circleIntegral`-based arguments).
Those live in residue_thm's analytic toolkit and would short-circuit
the stress test — the point is to exercise path-homotopy / quotient
group / monodromy reasoning, not to reuse a different topic's
contour-integral lemmas.
