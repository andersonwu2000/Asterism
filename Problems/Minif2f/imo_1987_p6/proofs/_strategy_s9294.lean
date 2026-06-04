import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs.L_prime_quadratic_extension

namespace Problems.Minif2f.imo_1987_p6

-- Strip the `f` indirection via `hf` and reduce to a single math core:
-- prove primality of `k^2 + k + p` for all `i ≤ p-2`, given the same primality
-- on the small initial segment `k ≤ ⌊√(p/3)⌋`. The closed-form quadratic version
-- is strictly more abstract: it eliminates the unknown function `f` entirely.
theorem s9294 : ∀ (p : ℕ) (f : ℕ → ℕ) (h₀ : ∀ x, f x = x ^ 2 + x + p) (h₀ : ∀ k : ℕ, k ≤ Nat.floor (Real.sqrt (p / 3)) → Nat.Prime (f k)), ∀ i ≤ p - 2, Nat.Prime (f i)  := by
  intro p f hf hk i hi
  have hk' : ∀ k, k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)) → Nat.Prime (k^2+k+p) := by
    intro k hkle
    have := hk k hkle
    rw [hf k] at this
    exact this
  have h_core := prime_quadratic_extension p hk'
  rw [hf i]
  exact h_core i hi

end Problems.Minif2f.imo_1987_p6
