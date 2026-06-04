import Mathlib
import Problems.Minif2f.amc12b_2002_p3.Defs
import Problems.Minif2f.amc12b_2002_p3.proofs.L_prime_expr_unique_three

namespace Problems.Minif2f.amc12b_2002_p3

-- Bridge to a pure number-theoretic claim: any n with 0 < n and Prime (n^2+2-3n)
-- must equal 3. Then S ⊆ {3} follows by unwrapping h₀ and using Finset.mem_singleton.
theorem s9477 (S : Finset ℕ)
    (h₀ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ Nat.Prime (n ^ 2 + 2 - 3 * n)) :
    S ⊆ ({3} : Finset ℕ)  := by
  have h_prime_expr_unique_three := prime_expr_unique_three
  intro n hn
  have h := (h₀ n).mp hn
  rw [Finset.mem_singleton]
  exact h_prime_expr_unique_three n h.1 h.2

end Problems.Minif2f.amc12b_2002_p3
