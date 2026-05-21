import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_g_tau_section_dw_eq_fderiv_apply_one_zero
import Problems.residue_thm.proofs.L_h_section_dw_eq_fderiv_apply_zero_one

namespace Problems.residue_thm

-- Same shape as the already-proved sibling s10364 (identical statement).
-- Two sub-goals (each matching an already-proved sibling lemma the framework
-- can alias on): (a) inner section-derivWithin identity for `H`, (b) τ-section
-- chain rule for the joint smooth `g`. Combine via `derivWithin_congr` (pointwise
-- rewrite on `Icc`).
theorem s10402
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ p ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1,
      derivWithin
          (fun τ'' => f (H τ'' p.1) * derivWithin (H τ'') (Set.Icc (0:ℝ) 1) p.1)
          (Set.Icc (0:ℝ) 1) p.2 =
      fderivWithin ℝ
        (fun q : ℝ × ℝ =>
          f (H q.1 q.2) *
            fderivWithin ℝ (fun r : ℝ × ℝ => H r.1 r.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) q ((0:ℝ), (1:ℝ)))
        (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (p.2, p.1) ((1:ℝ), (0:ℝ))  := by
  have h_inner :=
    h_section_dw_eq_fderiv_apply_zero_one hV hf hH hHV hH0 hH1
  have h_outer :=
    g_tau_section_dw_eq_fderiv_apply_one_zero hV hf hH hHV hH0 hH1

  intro p hp
  obtain ⟨ht, hτ⟩ := hp
  have h_fn_eq : Set.EqOn
      (fun τ'' => f (H τ'' p.1) * derivWithin (H τ'') (Set.Icc (0:ℝ) 1) p.1)
      (fun τ'' => f (H τ'' p.1) *
        fderivWithin ℝ (fun r : ℝ × ℝ => H r.1 r.2)
          (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ'', p.1) ((0:ℝ), (1:ℝ)))
      (Set.Icc (0:ℝ) 1) := by
    intro τ'' hτ''
    simp only [h_inner τ'' hτ'' p.1 ht]
  rw [derivWithin_congr h_fn_eq (h_fn_eq hτ)]
  exact h_outer p.2 hτ p.1 ht

end Problems.residue_thm
