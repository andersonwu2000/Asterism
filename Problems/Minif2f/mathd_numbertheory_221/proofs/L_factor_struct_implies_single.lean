import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_221

-- factor_struct_implies_single: support = {p} and value 2 at p forces factorization = single p 2
-- Uses Nat.support_factorization (support = primeFactors) + Finsupp.eq_single_iff.
theorem factor_struct_implies_single :
    ∀ x p : ℕ, x.primeFactors = {p} → x.factorization p = 2 →
      x.factorization = Finsupp.single p 2 := by
  intro x p hsupp hval
  rw [Finsupp.eq_single_iff]
  exact ⟨by rw [Nat.support_factorization, hsupp], hval⟩

end Problems.Minif2f.mathd_numbertheory_221
