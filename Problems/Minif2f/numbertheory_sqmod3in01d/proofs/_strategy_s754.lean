import Mathlib
import Problems.Minif2f.numbertheory_sqmod3in01d.Defs
import Problems.Minif2f.numbertheory_sqmod3in01d.proofs.L_sq_mod3_of_mod3_eq_one
import Problems.Minif2f.numbertheory_sqmod3in01d.proofs.L_sq_mod3_of_mod3_eq_two
import Problems.Minif2f.numbertheory_sqmod3in01d.proofs.L_sq_mod3_of_mod3_eq_zero

namespace Problems.Minif2f.numbertheory_sqmod3in01d

-- Case split on residue a % 3 ∈ {0,1,2} via omega, then dispatch
-- to a per-residue square computation. Each sub-goal is strictly
-- simpler: it adds a definite `a % 3 = k` hypothesis, reducing the
-- ∀ goal to a single modular arithmetic computation.
theorem s754 : ∀ (a : ℤ), a ^ 2 % 3 = 0 ∨ a ^ 2 % 3 = 1  := by
  intro a
  have h : a % 3 = 0 ∨ a % 3 = 1 ∨ a % 3 = 2 := by omega
  rcases h with h0 | h1 | h2
  · exact Or.inl (sq_mod3_of_mod3_eq_zero a h0)
  · exact Or.inr (sq_mod3_of_mod3_eq_one a h1)
  · exact Or.inr (sq_mod3_of_mod3_eq_two a h2)

end Problems.Minif2f.numbertheory_sqmod3in01d
