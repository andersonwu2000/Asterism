import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_inner_integral_tendsto_zero
import Problems.residue_thm.proofs.L_p_eq_inner_integral_cocompact

namespace Problems.residue_thm

-- Pick a fixed inner radius `R/2`, rewrite `P z` via `hP` for `z` far from `z₀`
-- (eventually in `cocompact ℂ`), then show the resulting parameter integral
-- tends to 0 as `z → ∞` and transport via `Tendsto.congr'`.
-- Sub-goal 1 drops `f`-analyticity and the cocompact/integral asymptotics.
-- Sub-goal 2 drops `P` and the pointwise integral identity.
theorem s10414
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0)  := by
  have h_eq : P =ᶠ[Filter.cocompact ℂ]
      (fun z => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, R/2), f w / (w - z))) :=
    p_eq_inner_integral_cocompact hR hf P hP
  have h_tendsto : Filter.Tendsto
      (fun z => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, R/2), f w / (w - z)))
      (Filter.cocompact ℂ) (nhds 0) :=
    inner_integral_tendsto_zero hR hf P hP
  exact h_tendsto.congr' h_eq.symm

end Problems.residue_thm
