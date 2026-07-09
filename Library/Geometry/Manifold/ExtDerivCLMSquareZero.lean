import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Mathlib.Analysis.Calculus.DifferentialForm.Basic
import Mathlib.Analysis.Distribution.TestFunction

/-!
# Exterior derivative CLM squaring to zero

This file defines `extDerivCLM`, the exterior derivative as a continuous linear map on
smooth compactly-supported test $k$-forms on an open subset $\Omega \subseteq E$, and proves
the fundamental identity $d \circ d = 0$ at the CLM level.

## Main definitions

- `extDerivCLM`: the exterior derivative $d_k \colon \mathcal{D}^\infty(\Omega, \Lambda^k) \to
  \mathcal{D}^\infty(\Omega, \Lambda^{k+1})$ as a continuous linear map.

## Main statements

- `extDerivCLM_comp_extDerivCLM_eq_zero`: $d_{k+1} \circ d_k = 0$ as CLMs.
-/

open TestFunction TopologicalSpace
open scoped Distributions ContDiff

namespace Library.Geometry.Manifold.ExtDerivCLMSquareZero

variable {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E] {Ω : Opens E}

/-- The exterior derivative as a continuous linear map on smooth compactly-supported test
$k$-forms on an open set $\Omega \subseteq E$,
$$d_k \colon \mathcal{D}^\infty(\Omega, \Lambda^k E^*) \to
  \mathcal{D}^\infty(\Omega, \Lambda^{k+1} E^*)$$
as a CLM. Built by composing `fderivCLM ℝ ⊤ ⊤` (the Fréchet derivative on test functions)
with `postcompCLM (alternatizeUncurryFinCLM …)` (which alternates the derivative to produce
`extDeriv`). Continuity in the LF test-form topology is automatic because compositions of CLMs
are CLMs. -/
noncomputable def extDerivCLM (k : ℕ) :
    𝓓^{(⊤ : ℕ∞)}(Ω, E [⋀^Fin k]→L[ℝ] ℝ) →L[ℝ]
      𝓓^{(⊤ : ℕ∞)}(Ω, E [⋀^Fin (k + 1)]→L[ℝ] ℝ) :=
  (postcompCLM (ContinuousAlternatingMap.alternatizeUncurryFinCLM ℝ E ℝ)) ∘L
    (fderivCLM ℝ ⊤ ⊤)

/-- **d² = 0**: composing the exterior derivative CLM with itself gives zero,
$(d_{k+1} \circ d_k) = 0$ as CLMs on $\mathcal{D}^\infty(\Omega, \Lambda^k E^*)$.
The proof reduces via `ext f x v` and `simp` to Mathlib's `extDeriv_extDeriv`. -/
theorem extDerivCLM_comp_extDerivCLM_eq_zero :
    ∀ {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E] {Ω : Opens E} (k : ℕ),
    (extDerivCLM (k + 1)).comp (extDerivCLM (Ω := Ω) k) = 0 := by
  intro E _ _ Ω k
  ext f x v
  simp only [ContinuousLinearMap.comp_apply, extDerivCLM,
    TestFunction.postcompCLM_apply, TestFunction.fderivCLM_apply_of_le (hk := le_top),
    ContinuousLinearMap.zero_apply]
  refine DFunLike.congr_fun (congrFun (extDeriv_extDeriv f.contDiff ?_) x) v
  norm_num [minSmoothness]
  exact WithTop.coe_le_coe.mpr le_top

end Library.Geometry.Manifold.ExtDerivCLMSquareZero
