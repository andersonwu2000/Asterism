import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct: restrict hH to the open Ioo×Ioo via mono, drop one order with
-- `ContDiffOn.fderiv_of_isOpen`, then post-compose with the continuous-linear
-- evaluation map `ContinuousLinearMap.apply ℝ ℂ (0,1)` to land on the
-- fderiv-applied form. No further sub-goals needed (leaf-bypass).
theorem s10356
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ContDiffOn ℝ 1
      (fun p : ℝ × ℝ => fderiv ℝ (fun q : ℝ × ℝ => H q.1 q.2) p (0, 1))
      (Set.Ioo (0:ℝ) 1 ×ˢ Set.Ioo (0:ℝ) 1)  := by
  have hHIoo : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
      (Set.Ioo (0:ℝ) 1 ×ˢ Set.Ioo (0:ℝ) 1) :=
    hH.mono (Set.prod_mono Set.Ioo_subset_Icc_self Set.Ioo_subset_Icc_self)
  have h_open : IsOpen (Set.Ioo (0:ℝ) 1 ×ˢ Set.Ioo (0:ℝ) 1) :=
    isOpen_Ioo.prod isOpen_Ioo
  have h_fderiv : ContDiffOn ℝ 1 (fderiv ℝ (fun q : ℝ × ℝ => H q.1 q.2))
      (Set.Ioo (0:ℝ) 1 ×ˢ Set.Ioo (0:ℝ) 1) :=
    hHIoo.fderiv_of_isOpen h_open (by norm_num)
  exact (ContinuousLinearMap.apply ℝ ℂ ((0:ℝ), (1:ℝ))).contDiff.comp_contDiffOn h_fderiv

end Problems.residue_thm
