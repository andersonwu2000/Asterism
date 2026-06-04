import Mathlib
import Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2.Defs

namespace Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2

-- Direct proof by strong induction: a 0 = 1 > 0 from h₀; for a (m+1), use h₁ m to
-- rewrite as ∏_{k<m+1} a k + 4, then Finset.prod_pos with the strong-induction
-- hypothesis on each factor gives the product > 0, and linarith closes via + 4.
theorem s9632 : ∀ (a : ℕ → ℝ) (_h₀ : a 0 = 1)
    (_h₁ : ∀ n, a (n + 1) = (∏ k ∈ Finset.range (n + 1), a k) + 4)
    (n : ℕ), 0 < a n  := by
  intro a h₀ h₁ n
  induction n using Nat.strong_induction_on with
  | _ n ih =>
    match n with
    | 0 => rw [h₀]; norm_num
    | m + 1 =>
      rw [h₁ m]
      have hprod : 0 < ∏ k ∈ Finset.range (m + 1), a k := by
        apply Finset.prod_pos
        intro k hk
        exact ih k (Finset.mem_range.mp hk)
      linarith

end Problems.Minif2f.numbertheory_aneqprodakp4_anmsqrtanp1eq2
