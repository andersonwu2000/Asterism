import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- boundary_partials_vanish: HasDerivWithinAt.congr + hasDerivWithinAt_const shows derivWithin = 0
-- hH0/hH1 force τ' ↦ H τ' 0 and τ' ↦ H τ' 1 constant on Icc 0 1, so both derivWithin vanish.
theorem boundary_partials_vanish
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ioo (0:ℝ) 1,
      f (H τ 1) * derivWithin (fun τ' => H τ' 1) (Set.Icc (0:ℝ) 1) τ
        - f (H τ 0) * derivWithin (fun τ' => H τ' 0) (Set.Icc (0:ℝ) 1) τ = 0 := by
  intro τ hτ
  have hτ_mem : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ioo_subset_Icc_self hτ
  have h1 : derivWithin (fun τ' => H τ' 1) (Set.Icc (0:ℝ) 1) τ = 0 := by
    have : HasDerivWithinAt (fun τ' => H τ' 1) 0 (Set.Icc (0:ℝ) 1) τ :=
      (hasDerivWithinAt_const τ (Set.Icc (0:ℝ) 1) (H 0 1)).congr
        (fun τ' hτ' => hH1 τ' hτ') (hH1 τ hτ_mem)
    exact this.derivWithin (uniqueDiffOn_Icc_zero_one τ hτ_mem)
  have h0 : derivWithin (fun τ' => H τ' 0) (Set.Icc (0:ℝ) 1) τ = 0 := by
    have : HasDerivWithinAt (fun τ' => H τ' 0) 0 (Set.Icc (0:ℝ) 1) τ :=
      (hasDerivWithinAt_const τ (Set.Icc (0:ℝ) 1) (H 0 0)).congr
        (fun τ' hτ' => hH0 τ' hτ') (hH0 τ hτ_mem)
    exact this.derivWithin (uniqueDiffOn_Icc_zero_one τ hτ_mem)
  rw [h1, h0]
  ring

end Problems.residue_thm
