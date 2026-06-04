import Mathlib
import Problems.Minif2f.imo_1967_p3.Defs

namespace Problems.Minif2f.imo_1967_p3

theorem main : ∀ (k m n : ℕ) (c : ℕ → ℕ) (h₀ : 0 < k ∧ 0 < m ∧ 0 < n) (h₁ : ∀ s, c s = s * (s + 1)) (h₂ : Nat.Prime (k + m + 1)) (h₃ : n + 1 < k + m + 1), (∏ i ∈ Finset.Icc 1 n, c i) ∣ ∏ i ∈ Finset.Icc 1 n, c (m + i) - c k := by sorry

end Problems.Minif2f.imo_1967_p3
