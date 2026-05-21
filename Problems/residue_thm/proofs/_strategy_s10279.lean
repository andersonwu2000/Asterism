import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_residue_via_integrals

namespace Problems.residue_thm

-- Cauchy residue theorem reduction: the integral-form residue theorem
-- `cauchy_residue_via_integrals` rewrites the LHS into a Finset sum of
-- `(∫ γ'/(γ-a)) · residue f a`. Each per-pole integral is then converted to
-- `2πi · windingNumber γ a` directly: `Complex.windingNumber` is defined as
-- `Classical.choose` on `h_winding a ha`, so `unfold; rw [dif_pos h_ex];
-- exact Classical.choose_spec h_ex` discharges that step inline (no forward
-- lemma dependency). `Finset.mul_sum` + `ring` close the algebraic shell.
theorem s10279
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (h_radius : ∀ a ∈ T, ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ f (Metric.ball a R \ {a}))
    (h_winding : ∀ a ∈ T, ∃ k : ℤ,
        (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 2 * Real.pi * Complex.I * k) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 2 * Real.pi * Complex.I *
      ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * Complex.residue f a  := by
  have h_resi := cauchy_residue_via_integrals hU hsc hT hf hγ hmap hclosed
  rw [h_resi, Finset.mul_sum]
  apply Finset.sum_congr rfl
  intro a ha
  have h_ex := h_winding a ha
  have hw : (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) =
      2 * Real.pi * Complex.I * (Complex.windingNumber γ a : ℂ) := by
    unfold Complex.windingNumber
    rw [dif_pos h_ex]
    exact Classical.choose_spec h_ex
  rw [hw]
  ring

end Problems.residue_thm
