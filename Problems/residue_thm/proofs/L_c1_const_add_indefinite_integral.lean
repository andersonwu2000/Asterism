import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- c1_const_add_indefinite_integral: ContDiff 1 via IccExtend + FTC-1 (HasDerivAt + congr_of_mem)
-- Extends v to a globally continuous w via Set.IccExtend, applies FTC-1 to get HasDerivAt for
-- integral of w, then transfers to integral of v via HasDerivWithinAt.congr_of_mem;
-- uses contDiffOn_one_iff_derivWithin with derivWithin = v from the HasDerivWithinAt witness.
theorem c1_const_add_indefinite_integral
    (c : ℂ) (v : ℝ → ℂ)
    (hv : ContinuousOn v (Set.Icc 0 1)) :
    ContDiffOn ℝ 1 (fun t : ℝ => c + ∫ s in (0:ℝ)..t, v s) (Set.Icc 0 1) := by
  apply ContDiffOn.add contDiffOn_const
  let vr : Set.Icc (0:ℝ) 1 → ℂ := Set.restrict (Set.Icc 0 1) v
  have hvr : Continuous vr := hv.restrict
  let w : ℝ → ℂ := Set.IccExtend (by norm_num : (0:ℝ) ≤ 1) vr
  have hw : Continuous w := hvr.Icc_extend'
  have hwv : ∀ t ∈ Set.Icc (0:ℝ) 1, w t = v t := fun t ht =>
    Set.IccExtend_of_mem _ vr ht
  have heq : ∀ t ∈ Set.Icc (0:ℝ) 1,
      (∫ s in (0:ℝ)..t, v s) = ∫ s in (0:ℝ)..t, w s := by
    intro t ht
    apply intervalIntegral.integral_congr
    intro s hs
    rw [Set.uIcc_of_le ht.1] at hs
    exact (hwv s ⟨hs.1, hs.2.trans ht.2⟩).symm
  have key : ∀ t ∈ Set.Icc (0:ℝ) 1,
      HasDerivWithinAt (fun t => ∫ s in (0:ℝ)..t, v s) (v t) (Set.Icc 0 1) t := by
    intro t ht
    have hDw : HasDerivAt (fun u => ∫ s in (0:ℝ)..u, w s) (w t) t :=
      intervalIntegral.integral_hasDerivAt_right (hw.intervalIntegrable 0 t)
        (hw.stronglyMeasurableAtFilter _ _) hw.continuousAt
    rw [hwv t ht] at hDw
    exact hDw.hasDerivWithinAt.congr_of_mem (fun u hu => heq u hu) ht
  rw [contDiffOn_one_iff_derivWithin (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1))]
  exact ⟨fun t ht => (key t ht).differentiableWithinAt,
    hv.congr fun t ht =>
      (key t ht).derivWithin (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1) t ht)⟩

end Problems.residue_thm