import Mathlib
import Problems.Minif2f.aime_1988_p4.Defs

namespace Problems.Minif2f.aime_1988_p4

-- sum_abs_lt_card: Finset.sum_lt_sum + n ≠ 0 (from h₁ ruling out empty sum) gives Σ|aₖ| < n
theorem sum_abs_lt_card : ∀ (n : ℕ) (a : ℕ → ℝ) (h₀ : ∀ n, abs (a n) < 1) (h₁ : (∑ k ∈ Finset.range n, abs (a k)) = 19 + abs (∑ k ∈ Finset.range n, a k)), (∑ k ∈ Finset.range n, abs (a k)) < (n : ℝ) := by
  intro n a h₀ h₁
  have hn : n ≠ 0 := by
    intro h
    simp [h] at h₁
  have hpos : 0 < n := Nat.pos_of_ne_zero hn
  have hlt : ∑ k ∈ Finset.range n, |a k| < ∑ k ∈ Finset.range n, (1 : ℝ) := by
    apply Finset.sum_lt_sum
    · intro k _
      exact le_of_lt (h₀ k)
    · exact ⟨0, Finset.mem_range.mpr hpos, h₀ 0⟩
  simp [Finset.sum_const, Finset.card_range, nsmul_eq_mul] at hlt
  exact hlt

end Problems.Minif2f.aime_1988_p4
