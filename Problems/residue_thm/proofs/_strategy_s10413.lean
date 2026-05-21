import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_p_differentiable_on_punctured_plane

namespace Problems.residue_thm

-- Reduce `AnalyticOn ℂ P` on the punctured plane to `DifferentiableOn ℂ P`
-- via Cauchy's `DifferentiableOn.analyticOn` (on the open set `Set.univ \ {z₀}`).
-- The single sub-goal abstracts away the analytic↔differentiable bridge:
-- Builder only needs to derive complex differentiability of `P` at each `z ≠ z₀`
-- from the local integral formula in `hP`, no power-series manipulation.
theorem s10413
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    AnalyticOn ℂ P (Set.univ \ {z₀})  := by
  have hdiff : DifferentiableOn ℂ P (Set.univ \ {z₀}) :=
    p_differentiable_on_punctured_plane hR hf P hP
  have hopen : IsOpen (Set.univ \ {z₀}) := by
    rw [Set.diff_eq, Set.univ_inter]; exact isOpen_compl_singleton
  exact hdiff.analyticOn hopen

end Problems.residue_thm
