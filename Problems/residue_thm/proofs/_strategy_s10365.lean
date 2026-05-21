import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_fderivwithin_h_apply10_section_hasderivwithinat

namespace Problems.residue_thm

-- Schwarz mixed-partial setup, chain-rule half.
-- Sub-goal `fderivwithin_h_apply10_section_hasderivwithinat` provides the same
-- chain-rule conclusion but stated as `HasDerivWithinAt` on `Icc 0 1` (the
-- natural domain on which the iterated `fderivWithin H` lives); we upgrade to
-- `HasDerivAt` here using `Set.Icc 0 1 ∈ 𝓝 t` which holds since `t ∈ Ioo 0 1`.
theorem s10365
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      HasDerivAt
        (fun t' => (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t')) (1, 0))
        ((fderivWithin ℝ (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t)) (0, 1) (1, 0)) t  := by
  intro τ hτ t ht
  have h_within :=
    fderivwithin_h_apply10_section_hasderivwithinat
      hV hf hH hHV hH0 hH1 τ hτ t ht
  exact h_within.hasDerivAt (Icc_mem_nhds ht.1 ht.2)

end Problems.residue_thm
