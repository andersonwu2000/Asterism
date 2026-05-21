import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c2_glue_pieces_inductive_helper

namespace Problems.residue_thm

-- Generalize over ht0/htn: prove the analogous statement for arbitrary
-- t : ℕ → ℝ on Icc (t 0) (t n) via induction on n (sub-goal
-- `c2_glue_pieces_inductive_helper`), then rewrite the domain to Icc 0 1
-- using ht0 and htn.
theorem s10577
    {n : ℕ} (t : ℕ → ℝ) (p : ℕ → ℂ)
    (ht0 : t 0 = 0) (htn : t n = 1)
    (htmono : ∀ i, i < n → t i ≤ t (i + 1))
    (hp_collapse : ∀ i, i < n → t i = t (i + 1) → p i = p (i + 1)) :
    ∀ (ψ : ℕ → ℝ → ℂ),
      (∀ i, i < n →
        ContDiffOn ℝ 2 (ψ i) (Set.Icc (t i) (t (i + 1))) ∧
        ψ i (t i) = p i ∧
        ψ i (t (i + 1)) = p (i + 1) ∧
        Set.MapsTo (ψ i) (Set.Icc (t i) (t (i + 1))) (segment ℝ (p i) (p (i + 1))) ∧
        derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))) (t i) = 0 ∧
        derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))) (t (i + 1)) = 0 ∧
        derivWithin (derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))))
            (Set.Icc (t i) (t (i + 1))) (t i) = 0 ∧
        derivWithin (derivWithin (ψ i) (Set.Icc (t i) (t (i + 1))))
            (Set.Icc (t i) (t (i + 1))) (t (i + 1)) = 0) →
      ∃ (η : ℝ → ℂ),
        ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
        (∀ i, i ≤ n → η (t i) = p i) ∧
        (∀ i, i < n →
          Set.MapsTo η (Set.Icc (t i) (t (i + 1))) (segment ℝ (p i) (p (i + 1))))  := by
  intro ψ hψ
  have h_helper :=
    c2_glue_pieces_inductive_helper t p htmono hp_collapse ψ hψ
  obtain ⟨η, hC2, hpt, hmap⟩ := h_helper
  refine ⟨η, ?_, hpt, hmap⟩
  have hicc : Set.Icc (t 0) (t n) = Set.Icc (0:ℝ) 1 := by rw [ht0, htn]
  rwa [hicc] at hC2

end Problems.residue_thm
