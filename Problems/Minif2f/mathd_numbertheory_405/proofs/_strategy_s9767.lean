import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs

namespace Problems.Minif2f.mathd_numbertheory_405

-- Direct pair-invariant induction (mirrors s9741's body, no unused (a, h₃)).
-- Base `t 16 % 7 = 0 ∧ t 17 % 7 = 1` by unrolling hrec at 2..17 + omega.
-- Step: 1st conjunct = ih.2 after `k+1+16 = k+17`; 2nd uses hrec at k+18, k+2
-- then `rw [Nat.add_mod, ih.1, ih.2, ← Nat.add_mod]`.
theorem s9767 (t : ℕ → ℕ) (h₀ : t 0 = 0) (h₁ : t 1 = 1)
    (h₂ : ∀ n > 1, t n = t (n - 2) + t (n - 1)) :
    ∀ m, t (m + 16) % 7 = t m % 7 ∧ t (m + 17) % 7 = t (m + 1) % 7  := by
  have h_base : t 16 % 7 = 0 ∧ t 17 % 7 = 1 := by
    have h2 : t 2 = t 0 + t 1 := by have := h₂ 2 (by norm_num); simp at this; exact this
    have h3 : t 3 = t 1 + t 2 := by have := h₂ 3 (by norm_num); simp at this; exact this
    have h4 : t 4 = t 2 + t 3 := by have := h₂ 4 (by norm_num); simp at this; exact this
    have h5 : t 5 = t 3 + t 4 := by have := h₂ 5 (by norm_num); simp at this; exact this
    have h6 : t 6 = t 4 + t 5 := by have := h₂ 6 (by norm_num); simp at this; exact this
    have h7 : t 7 = t 5 + t 6 := by have := h₂ 7 (by norm_num); simp at this; exact this
    have h8 : t 8 = t 6 + t 7 := by have := h₂ 8 (by norm_num); simp at this; exact this
    have h9 : t 9 = t 7 + t 8 := by have := h₂ 9 (by norm_num); simp at this; exact this
    have h10 : t 10 = t 8 + t 9 := by have := h₂ 10 (by norm_num); simp at this; exact this
    have h11 : t 11 = t 9 + t 10 := by have := h₂ 11 (by norm_num); simp at this; exact this
    have h12 : t 12 = t 10 + t 11 := by have := h₂ 12 (by norm_num); simp at this; exact this
    have h13 : t 13 = t 11 + t 12 := by have := h₂ 13 (by norm_num); simp at this; exact this
    have h14 : t 14 = t 12 + t 13 := by have := h₂ 14 (by norm_num); simp at this; exact this
    have h15 : t 15 = t 13 + t 14 := by have := h₂ 15 (by norm_num); simp at this; exact this
    have h16 : t 16 = t 14 + t 15 := by have := h₂ 16 (by norm_num); simp at this; exact this
    have h17 : t 17 = t 15 + t 16 := by have := h₂ 17 (by norm_num); simp at this; exact this
    omega
  intro m
  induction m with
  | zero =>
    refine ⟨?_, ?_⟩
    · change t (0 + 16) % 7 = t 0 % 7
      simp [h₀, h_base.1]
    · change t (0 + 17) % 7 = t 1 % 7
      simp [h₁, h_base.2]
  | succ k ih =>
    refine ⟨?_, ?_⟩
    · have heq : k + 1 + 16 = k + 17 := by ring
      rw [heq]
      exact ih.2
    · have heq1 : k + 1 + 17 = k + 18 := by ring
      have heq2 : k + 1 + 1 = k + 2 := by ring
      rw [heq1, heq2]
      have hr18 : t (k + 18) = t (k + 16) + t (k + 17) := by
        have h := h₂ (k + 18) (by omega)
        have e1 : k + 18 - 2 = k + 16 := by omega
        have e2 : k + 18 - 1 = k + 17 := by omega
        rw [e1, e2] at h
        exact h
      have hr2 : t (k + 2) = t k + t (k + 1) := by
        have h := h₂ (k + 2) (by omega)
        have e1 : k + 2 - 2 = k := by omega
        have e2 : k + 2 - 1 = k + 1 := by omega
        rw [e1, e2] at h
        exact h
      rw [hr18, hr2, Nat.add_mod, ih.1, ih.2, ← Nat.add_mod]

end Problems.Minif2f.mathd_numbertheory_405
