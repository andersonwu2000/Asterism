import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

open Filter Set Topology

-- entry_kind: Builder
-- endpoint_eq_of_continuous_deriv_zero_ioo: G 0 = G 1 from ContinuousOn on Icc and HasDerivAt 0
-- on Ioo; G is constant on Ioo by IsOpen.is_const_of_deriv_eq_zero, then extended to endpoints
-- via the nhdsWithin_Ioo_eq_nhdsGT/LT filter identities and tendsto_nhds_unique.
theorem endpoint_eq_of_continuous_deriv_zero_ioo
    {G : ℝ → ℂ}
    (hcont : ContinuousOn G (Icc (0 : ℝ) 1))
    (hderiv : ∀ τ ∈ Ioo (0 : ℝ) 1, HasDerivAt G 0 τ) :
    G 0 = G 1 := by
  have hDiff : DifferentiableOn ℝ G (Ioo (0 : ℝ) 1) := fun τ hτ =>
    (hderiv τ hτ).differentiableAt.differentiableWithinAt
  have hZero : EqOn (deriv G) 0 (Ioo (0 : ℝ) 1) := fun τ hτ => (hderiv τ hτ).deriv
  obtain ⟨c, hc⟩ := isOpen_Ioo.exists_is_const_of_deriv_eq_zero isPreconnected_Ioo hDiff hZero
  haveI hnebot0 : (nhdsWithin (0 : ℝ) (Ioo 0 1)).NeBot := by
    rw [nhdsWithin_Ioo_eq_nhdsGT (by norm_num : (0 : ℝ) < 1)]; infer_instance
  haveI hnebot1 : (nhdsWithin (1 : ℝ) (Ioo 0 1)).NeBot := by
    rw [nhdsWithin_Ioo_eq_nhdsLT (by norm_num : (0 : ℝ) < 1)]; infer_instance
  have htendG0 : Tendsto G (nhdsWithin (0 : ℝ) (Ioo 0 1)) (nhds (G 0)) :=
    (hcont.continuousWithinAt (left_mem_Icc.mpr zero_le_one)).mono_left
      (nhdsWithin_mono _ Ioo_subset_Icc_self)
  have htendc0 : Tendsto G (nhdsWithin (0 : ℝ) (Ioo 0 1)) (nhds c) :=
    tendsto_const_nhds.congr' (eventually_nhdsWithin_of_forall (fun x hx => (hc x hx).symm))
  have h0 : G 0 = c := tendsto_nhds_unique htendG0 htendc0
  have htendG1 : Tendsto G (nhdsWithin (1 : ℝ) (Ioo 0 1)) (nhds (G 1)) :=
    (hcont.continuousWithinAt (right_mem_Icc.mpr zero_le_one)).mono_left
      (nhdsWithin_mono _ Ioo_subset_Icc_self)
  have htendc1 : Tendsto G (nhdsWithin (1 : ℝ) (Ioo 0 1)) (nhds c) :=
    tendsto_const_nhds.congr' (eventually_nhdsWithin_of_forall (fun x hx => (hc x hx).symm))
  have h1 : G 1 = c := tendsto_nhds_unique htendG1 htendc1
  rw [h0, h1]

end Problems.residue_thm