import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- f_h_joint_contdiff_one: f∘H is C¹ on Icc×Icc via analyticity + composition
-- f is ℝ-smooth (restrict_scalars from ℂ-analyticity); H is C² hence C¹; compose.
-- entry_kind: Builder
theorem f_h_joint_contdiff_one
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ContDiffOn ℝ 1
      (fun p : ℝ × ℝ => f (H p.1 p.2))
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) := by
  have hfR : ContDiffOn ℝ 1 f V := by
    set_option backward.isDefEq.respectTransparency false in
    exact (hf.contDiffOn_of_completeSpace (n := 1)).restrict_scalars ℝ
  have hmaps : Set.MapsTo (fun p : ℝ × ℝ => H p.1 p.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) V :=
    fun p ⟨h1, h2⟩ => hHV p.1 h1 p.2 h2
  exact hfR.comp (hH.of_le (by norm_num)) hmaps
end Problems.residue_thm
