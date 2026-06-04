import Mathlib
import Problems.Minif2f.amc12a_2002_p21.Defs

namespace Problems.Minif2f.amc12a_2002_p21

theorem main : ∀ (u : ℕ → ℕ) (h₀ : u 0 = 4) (h₁ : u 1 = 7) (h₂ : ∀ n ≥ 2, u (n + 2) = (u n + u (n + 1)) % 10), ∀ n, (∑ k ∈ Finset.range n, u k) > 10000 → 1999 ≤ n := by sorry

end Problems.Minif2f.amc12a_2002_p21
