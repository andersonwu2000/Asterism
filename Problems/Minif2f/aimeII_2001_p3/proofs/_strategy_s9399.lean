import Mathlib
import Problems.Minif2f.aimeII_2001_p3.Defs

namespace Problems.Minif2f.aimeII_2001_p3

-- Chain anti-period-5 twice: x(n+10) = x((n+5)+5) = -x(n+5) = -(-x n) = x n.
-- anti_period_5 inlined (2 unfoldings of h₆ at n+5 and n+4); outer chain then
-- linarith closes the parent.
theorem s9399 (x : ℕ → ℤ) (h₀ : x 1 = 211) (h₂ : x 2 = 375) (h₃ : x 3 = 420)
    (h₄ : x 4 = 523)
    (h₆ : ∀ n ≥ 5, x n = x (n - 1) - x (n - 2) + x (n - 3) - x (n - 4)) :
    ∀ n, 1 ≤ n → x (n + 10) = x n  := by
  have h_anti : ∀ n, 1 ≤ n → x (n + 5) = -x n := by
    intro n hn
    have h5 := h₆ (n + 5) (by omega)
    have h4 := h₆ (n + 4) (by omega)
    simp only [show n + 5 - 1 = n + 4 from by omega,
               show n + 5 - 2 = n + 3 from by omega,
               show n + 5 - 3 = n + 2 from by omega,
               show n + 5 - 4 = n + 1 from by omega,
               show n + 4 - 1 = n + 3 from by omega,
               show n + 4 - 2 = n + 2 from by omega,
               show n + 4 - 3 = n + 1 from by omega,
               show n + 4 - 4 = n from by omega] at h5 h4
    linarith
  intro n hn
  have h1 := h_anti n hn
  have h2 := h_anti (n + 5) (by omega)
  have hEq : n + 5 + 5 = n + 10 := by omega
  rw [hEq] at h2
  linarith

end Problems.Minif2f.aimeII_2001_p3
