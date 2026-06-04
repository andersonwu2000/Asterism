import Mathlib
import Problems.Minif2f.induction_seq_mul2pnp1.Defs

namespace Problems.Minif2f.induction_seq_mul2pnp1

-- Direct induction on n: base case via h₀; succ step rewrites with h₁ and ih, closed by omega
-- after supplying 2^(k+2) = 2·2^(k+1) and the bound k+2 ≤ 2^(k+1) (inner induction on k).
theorem s626 : ∀ (n : ℕ) (u : ℕ → ℕ) (h₀ : u 0 = 0) (h₁ : ∀ n, u (n + 1) = 2 * u n + (n + 1)), u n = 2 ^ (n + 1) - (n + 2)  := by
  intro n u h₀ h₁
  induction n with
  | zero => simp [h₀]
  | succ k ih =>
      have h2 : 2 ^ (k + 1 + 1) = 2 * 2 ^ (k + 1) := by ring
      have hge : k + 2 ≤ 2 ^ (k + 1) := by
        clear ih h₁ h₀
        induction k with
        | zero => decide
        | succ j jh =>
          have hj : 2 ^ (j + 1 + 1) = 2 * 2 ^ (j + 1) := by ring
          omega
      rw [h₁ k, ih]
      omega

end Problems.Minif2f.induction_seq_mul2pnp1
