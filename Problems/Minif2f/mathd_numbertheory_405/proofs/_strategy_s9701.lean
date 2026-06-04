import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs.L_base_16_17_mod_7

namespace Problems.Minif2f.mathd_numbertheory_405

-- Direct induction on m using the strengthened pair invariant.
-- Sub-goal `base_16_17_mod_7` is the base case (t 16 % 7 = 0, t 17 % 7 = 1).
-- Inductive step: first conjunct is `ih.2`; second uses hrec at k+18 to unfold
-- t (k+18) = t (k+16) + t (k+17) and matches t (k+2) = t k + t (k+1) modulo 7.
theorem s9701 :
    ∀ (t : ℕ → ℕ),
      t 0 = 0 →
      t 1 = 1 →
      (∀ n > 1, t n = t (n - 2) + t (n - 1)) →
      ∀ m, t (m + 16) % 7 = t m % 7 ∧ t (m + 17) % 7 = t (m + 1) % 7  := by
  intro t ht0 ht1 hrec
  have h_base : t 16 % 7 = 0 ∧ t 17 % 7 = 1 := base_16_17_mod_7 t ht0 ht1 hrec
  intro m
  induction m with
  | zero =>
    refine ⟨?_, ?_⟩
    · change t (0 + 16) % 7 = t 0 % 7
      simp [ht0, h_base.1]
    · change t (0 + 17) % 7 = t 1 % 7
      simp [ht1, h_base.2]
  | succ k ih =>
    refine ⟨?_, ?_⟩
    · have heq : k + 1 + 16 = k + 17 := by ring
      rw [heq]
      exact ih.2
    · have heq1 : k + 1 + 17 = k + 18 := by ring
      have heq2 : k + 1 + 1 = k + 2 := by ring
      rw [heq1, heq2]
      have hr18 : t (k + 18) = t (k + 16) + t (k + 17) := by
        have h := hrec (k + 18) (by omega)
        have e1 : k + 18 - 2 = k + 16 := by omega
        have e2 : k + 18 - 1 = k + 17 := by omega
        rw [e1, e2] at h
        exact h
      have hr2 : t (k + 2) = t k + t (k + 1) := by
        have h := hrec (k + 2) (by omega)
        have e1 : k + 2 - 2 = k := by omega
        have e2 : k + 2 - 1 = k + 1 := by omega
        rw [e1, e2] at h
        exact h
      rw [hr18, hr2, Nat.add_mod, ih.1, ih.2, ← Nat.add_mod]

end Problems.Minif2f.mathd_numbertheory_405
