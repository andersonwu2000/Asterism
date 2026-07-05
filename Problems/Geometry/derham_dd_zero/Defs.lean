import Mathlib

open scoped Distributions ContDiff
open TestFunction TopologicalSpace

namespace Problems.Geometry.derham_dd_zero

variable {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E] {Ω : Opens E}

/-- The exterior derivative as a CONTINUOUS linear map on test k-forms
(`𝓓^∞(Ω, Λ^k) →L 𝓓^∞(Ω, Λ^{k+1})`), the d-operator of the de Rham complex at the
test-form level. Built by composing three existing Mathlib CLMs — so its
continuity in the LF test-form topology is automatic (a composition of CLMs is a
CLM):
  * `fderivCLM ℝ ⊤ ⊤` : the Fréchet derivative as a CLM on test functions;
  * `postcompCLM (alternatizeUncurryFinCLM …)` : postcompose with the alternation
    map (which turns `fderiv` into the exterior derivative `extDeriv`).
This is the one operator the de Rham currents foundation needs that Mathlib does
not package directly. (Per-decl `noncomputable` — NOT a `noncomputable section` —
so the Librarian migrate's decl extraction preserves the modifier.) -/
noncomputable def extDerivCLM (k : ℕ) :
    𝓓^{(⊤ : ℕ∞)}(Ω, E [⋀^Fin k]→L[ℝ] ℝ) →L[ℝ]
      𝓓^{(⊤ : ℕ∞)}(Ω, E [⋀^Fin (k + 1)]→L[ℝ] ℝ) :=
  (postcompCLM (ContinuousAlternatingMap.alternatizeUncurryFinCLM ℝ E ℝ)) ∘L
    (fderivCLM ℝ ⊤ ⊤)

end Problems.Geometry.derham_dd_zero
