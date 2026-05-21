import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integral_partial_fractions_split
import Problems.residue_thm.proofs.L_subtracted_integrand_integral_zero

namespace Problems.residue_thm

-- Partial-fractions decomposition: subtract the polar parts
-- `∑ a ∈ T, residue(f, a) / (z - a)` from `f`; the corrected integrand
-- integrates to zero (Cauchy on simply connected `U` after removable-
-- singularity extension), and integral linearity rewrites the difference
-- against `γ'` as `∫ f γ' − ∑ residue · ∫ γ'/(γ-a)`. Combining the two
-- yields the stated identity.
theorem s10283
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0 : ℝ)..1, f (γ t) * deriv γ t) =
      ∑ a ∈ T, (∫ t in (0 : ℝ)..1, deriv γ t / (γ t - a)) * Complex.residue f a  := by
  have h_zero := subtracted_integrand_integral_zero hU hsc hT hf hγ hmap hclosed
  have h_split := integral_partial_fractions_split hU hsc hT hf hγ hmap hclosed
  have h_eq : (∫ t in (0 : ℝ)..1, f (γ t) * deriv γ t) -
      ∑ a ∈ T, (∫ t in (0 : ℝ)..1, deriv γ t / (γ t - a)) * Complex.residue f a = 0 := by
    rw [← h_split]; exact h_zero
  exact sub_eq_zero.mp h_eq

end Problems.residue_thm
