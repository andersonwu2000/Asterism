import Mathlib
import Problems.Minif2f.mathd_numbertheory_303.Defs
import Problems.Minif2f.mathd_numbertheory_303.proofs.L_s_eq_explicit_finset

namespace Problems.Minif2f.mathd_numbertheory_303

-- Reduce to: S = {7, 13, 91} as explicit Finset, then evaluate the sum.
-- Sub-goal proves S = {7, 13, 91}; `decide` closes 7+13+91=111 after rewrite.
theorem s718 : ∀ (S : Finset ℕ) (h₀ : ∀ n : ℕ, n ∈ S ↔ 2 ≤ n ∧ 171 ≡ 80 [MOD n] ∧ 468 ≡ 13 [MOD n]), (∑ k ∈ S, k) = 111  := by
  intro S h₀
  have h_set : S = ({7, 13, 91} : Finset ℕ) := s_eq_explicit_finset S h₀
  rw [h_set]
  decide

end Problems.Minif2f.mathd_numbertheory_303
