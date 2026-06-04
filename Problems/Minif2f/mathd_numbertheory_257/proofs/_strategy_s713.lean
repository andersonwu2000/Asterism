import Mathlib
import Problems.Minif2f.mathd_numbertheory_257.Defs

namespace Problems.Minif2f.mathd_numbertheory_257

-- Direct closed-form proof: ∑ k ∈ Finset.range 101, k = 5050 (Gauss sum), so
-- the hypothesis becomes 77 ∣ 5050 - x with 1 ≤ x ≤ 100. Since 5050 = 77·65 + 45,
-- the unique solution in the range is x = 45 (next candidate 45+77 = 122 > 100).
-- Sum is evaluated by `decide`; remaining linear-divisibility goal closed by `omega`.
theorem s713 : ∀ (x : ℕ) (h₀ : 1 ≤ x ∧ x ≤ 100) (h₁ : 77 ∣ (∑ k ∈ Finset.range 101, k) - x), x = 45  := by
  intro x ⟨h₀l, h₀r⟩ h₁
  have hsum : ∑ k ∈ Finset.range 101, k = 5050 := by decide
  rw [hsum] at h₁
  omega

end Problems.Minif2f.mathd_numbertheory_257
