import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- seg_f_comp_hasderivat_ioo: chain rule for F∘(t↦z+t·(w-z)) on Ioo 0 1 via
-- complex HasDerivAt.comp then HasDerivAt.comp_ofReal to land in ℝ→ℂ
theorem seg_f_comp_hasderivat_ioo
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    {z w : ℂ}
    (hz : z ∈ Metric.ball z₀ R)
    (hw : w ∈ Metric.ball z₀ R) :
    ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt (fun t : ℝ => F (z + (t:ℂ) * (w - z)))
        (f (z + (t:ℂ) * (w - z)) * (w - z)) t := by
  intro t ht
  have hmem : z + (t:ℂ) * (w - z) ∈ Metric.ball z₀ R := by
    have h : (1 - (t:ℝ)) • z + (t:ℝ) • w ∈ Metric.ball z₀ R :=
      (convex_ball z₀ R) hz hw (sub_nonneg.mpr ht.2.le) ht.1.le (by ring)
    simp only [RCLike.real_smul_eq_coe_mul] at h
    have heq : ((1 - (t:ℝ) : ℝ) : ℂ) * z + ((t:ℝ) : ℂ) * w = z + (t:ℂ) * (w - z) := by
      push_cast; ring
    rw [← heq]; exact h
  have hFder : HasDerivAt F (f (z + ↑t * (w - z))) (z + ↑t * (w - z)) := hF _ hmem
  have hGs : HasDerivAt (fun s : ℂ => z + s * (w - z)) (w - z) (t : ℂ) := by
    have h1 : HasDerivAt (fun s : ℂ => s * (w - z)) (1 * (w - z)) (t : ℂ) :=
      (hasDerivAt_id (t : ℂ)).mul_const (w - z)
    simp only [one_mul] at h1
    exact h1.const_add z
  have hH : HasDerivAt (fun s : ℂ => F (z + s * (w - z)))
      (f (z + ↑t * (w - z)) * (w - z)) (t : ℂ) :=
    hFder.comp (t : ℂ) hGs
  exact hH.comp_ofReal

end Problems.residue_thm
