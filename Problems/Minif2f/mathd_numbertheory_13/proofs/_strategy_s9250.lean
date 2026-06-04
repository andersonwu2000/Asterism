import Mathlib
import Problems.Minif2f.mathd_numbertheory_13.Defs
import Problems.Minif2f.mathd_numbertheory_13.proofs.L_v_ge_89
import Problems.Minif2f.mathd_numbertheory_13.proofs.L_v_le_89

namespace Problems.Minif2f.mathd_numbertheory_13

-- Decompose v = 89 via two-sided bound: v ≤ 89 and 89 ≤ v.
-- Combine the two bounds with Nat.le_antisymm — each bound is a simpler
-- inequality than the full equality.
theorem s9250 : ∀ (u v : ℕ) (S : Set ℕ) (_ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ 14 * n % 100 = 46) (_ : IsLeast S u) (_ : IsLeast (S \ {u}) v), v = 89  := by
  intro u v S h₀ h₁ h₂
  have h_le : v ≤ 89 := v_le_89 u v S h₀ h₁ h₂
  have h_ge : 89 ≤ v := v_ge_89 u v S h₀ h₁ h₂
  exact Nat.le_antisymm h_le h_ge

end Problems.Minif2f.mathd_numbertheory_13
