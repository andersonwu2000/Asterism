import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_path_int_eq_residue_times_winding_int
import Problems.residue_thm.proofs.L_winding_integral_formula

namespace Problems.residue_thm

-- Reduce the residue integral identity to two independent pieces:
--   (A) winding_integral_formula (Builder leaf): ∫₀¹ γ'(t)/(γ(t) - a) dt = 2πi · winding γ a
--       — direct from the windingNumber definition and `exists_winding_integer`.
--   (B) path_int_eq_residue_times_winding_int (Backward): the substantive residue identity
--       ∫₀¹ P(γt)·γ'(t) dt = residue P a · ∫₀¹ γ'(t)/(γt - a) dt — decouples residue from
--       winding so the proof can build a primitive of `P(z) - residue P a / (z - a)` on
--       ℂ \ {a} (zero residue ⇒ exact on the punctured plane) without re-doing the dead
--       Fubini/Cauchy-repr routes.
-- Combinator: rewrite via (B) then (A), then ring to commute the factors.
theorem s10474
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t) =
      2 * Real.pi * Complex.I *
        ((Complex.windingNumber γ a : ℂ) * Complex.residue P a)  := by
  have hA := winding_integral_formula hγ h_avoid hclosed
  have hB := path_int_eq_residue_times_winding_int hP hP_tendsto hγ h_avoid hclosed
  rw [hB, hA]
  ring

end Problems.residue_thm
