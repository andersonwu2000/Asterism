import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_chord_segment_form_primdiff

namespace Problems.residue_thm

-- Convert the lerp form `(1-s)·z + s·w` to the offset form `z + s·(w-z)`
-- pointwise (pure `ring` after `push_cast`), then apply the offset-form FTC
-- specialization `chord_segment_form_primdiff` which packages the standard
-- chain-rule + `integral_eq_sub_of_hasDerivAt_of_le` argument for the convex
-- ball case (companion of the already-proved `segment_integral_eq_primitive_diff_in_ball`).
theorem s10645
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    {z w : ℂ}
    (hz : z ∈ Metric.ball z₀ R)
    (hw : w ∈ Metric.ball z₀ R) :
    (∫ s in (0:ℝ)..1, f ((1 - (s:ℂ)) * z + (s:ℂ) * w) * (w - z)) = F w - F z  := by
  have h_seg : (∫ s in (0:ℝ)..1, f (z + (s:ℂ) * (w - z)) * (w - z)) = F w - F z :=
    chord_segment_form_primdiff hF hz hw
  have h_pointwise : ∀ s ∈ Set.uIcc (0:ℝ) 1,
      f ((1 - (s:ℂ)) * z + (s:ℂ) * w) * (w - z)
        = f (z + (s:ℂ) * (w - z)) * (w - z) := by
    intro s _
    congr 2
    ring
  calc (∫ s in (0:ℝ)..1, f ((1 - (s:ℂ)) * z + (s:ℂ) * w) * (w - z))
      = (∫ s in (0:ℝ)..1, f (z + (s:ℂ) * (w - z)) * (w - z)) :=
        intervalIntegral.integral_congr h_pointwise
    _ = F w - F z := h_seg
end Problems.residue_thm
