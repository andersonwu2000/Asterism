import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- pointwise_integrand_decomp: rewrite f(γt)·γ' using hpw, distribute mul over add and sum
-- entry_kind: Builder
theorem pointwise_integrand_decomp
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ)
    (hg : AnalyticOn ℂ g U)
    (hPa : ∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a}))
    (hpw : ∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z) :
    ∀ t ∈ Set.Icc (0:ℝ) 1,
      f (γ t) * deriv γ t =
        g (γ t) * deriv γ t + ∑ a ∈ T, P a (γ t) * deriv γ t := by
  intro t ht
  have heq := hpw (γ t) (hmaps ht)
  rw [heq, add_mul, Finset.sum_mul]

end Problems.residue_thm
