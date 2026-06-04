import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs

namespace Problems.Minif2f.mathd_numbertheory_221

-- factorization_eq_two_of_singleton: rewrite primeFactors singleton into product, simp to
-- scalar equation, omega closes y.factorization p + 1 = 3 → y.factorization p = 2
theorem factorization_eq_two_of_singleton :
    ∀ y p : ℕ, y ≠ 0 → y.primeFactors = {p} →
      (∏ q ∈ y.primeFactors, (y.factorization q + 1)) = 3 →
      y.factorization p = 2 := by
  intro y p hy hpf hprod
  rw [hpf] at hprod
  simp at hprod
  omega

end Problems.Minif2f.mathd_numbertheory_221
