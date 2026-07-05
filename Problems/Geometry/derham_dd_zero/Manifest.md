---
problem: Geometry.derham_dd_zero
library: true
axioms_whitelist:
  - propext
  - Quot.sound
  - Classical.choice
forbidden_lemmas: []
---

# Geometry.derham_dd_zero — d∘d = 0 for the test-form exterior-derivative CLM

## Statement
For the continuous-linear exterior derivative `extDerivCLM` on smooth compactly-
supported test k-forms on an open `Ω ⊆ E` (see `Defs.lean`),

`(extDerivCLM (k+1)) ∘ (extDerivCLM k) = 0`

i.e. `d∘d = 0` of the de Rham complex, realized at the level of the
continuous-linear-map operator on the LF test-form space.

## Setting
First brick of the **de Rham currents** program: a k-current is a continuous
linear functional on test k-forms, and the boundary `∂T := T ∘ extDerivCLM`. The
currents' `∂∘∂ = 0` is the dual (precomposition) corollary of THIS `d∘d = 0`.
`extDerivCLM` is given in `Defs.lean` (a composition of Mathlib CLMs —
`fderivCLM`, `postcompCLM`, `alternatizeUncurryFinCLM` — so its continuity is
automatic). This problem is the analytic core: proving the operator squares to
zero. It is a **probe** of whether the framework can do test-function /
distribution functional analysis (a domain not previously exercised).

## Strategic notes
Two continuous linear maps into a normed space are equal iff they agree on every
input (`ContinuousLinearMap.ext`); two test functions are equal iff their
underlying functions agree (`TestFunction.ext` / `DFunLike.ext`). So the goal
reduces, for a test form `f` and a point `x`, to a pointwise identity on the
underlying functions. Unfold `extDerivCLM f` via `fderivCLM_apply` +
`postcompCLM_apply`: its underlying function is `extDeriv f.toFun`
(`extDeriv ω x = alternatizeUncurryFin (fderiv ℝ ω x)`). The goal then becomes
`extDeriv (extDeriv f) = 0`, which is Mathlib's `extDeriv_extDeriv` (the C∞
hypothesis holds: a test function is `ContDiff ℝ ∞`, and `minSmoothness ℝ 2 ≤ ⊤`).

## Lemma hints
- `extDeriv_extDeriv` : `extDeriv (extDeriv ω) = 0` for `ContDiff ℝ r ω`, `minSmoothness ℝ 2 ≤ r` — the pointwise d∘d=0 the whole proof reduces to.
- `TestFunction.fderivCLM_apply` : underlying function of `fderivCLM` is `fderiv ℝ`.
- `TestFunction.postcompCLM_apply` : underlying function of `postcompCLM T` is `T ∘ ·`.
- `ContinuousLinearMap.ext` : two CLMs equal iff pointwise equal.
- `ContinuousAlternatingMap.alternatizeUncurryFinCLM` : the alternation CLM; `extDeriv ω x = alternatizeUncurryFin (fderiv ℝ ω x)`.
- `extDeriv` (`Mathlib.Analysis.Calculus.DifferentialForm.Basic`) : the flat exterior derivative on a normed space.
