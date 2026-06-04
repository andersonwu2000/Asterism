import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs

namespace Problems.Minif2f.mathd_numbertheory_709

-- decompose_n_two_three_coprime: any n > 0 factors as 2^a * 3^b * r with r coprime to 6,
-- using a = v₂(n), b = v₃(n), r = n / (2^a * 3^b); coprimality from factorization = 0.
theorem decompose_n_two_three_coprime :
    ∀ (n : ℕ) (_h₀ : 0 < n)
      (_h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
      (_h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
      ∃ a b r, n = 2 ^ a * 3 ^ b * r ∧ Nat.Coprime r 6 ∧ 0 < r := by
  intro n h₀ _h₁ _h₂
  have h23dvd : 2 ^ n.factorization 2 * 3 ^ n.factorization 3 ∣ n := by
    apply Nat.Coprime.mul_dvd_of_dvd_of_dvd
    · apply Nat.Coprime.pow_left; apply Nat.Coprime.pow_right; norm_num
    · exact Nat.ordProj_dvd n 2
    · exact Nat.ordProj_dvd n 3
  let r := n / (2 ^ n.factorization 2 * 3 ^ n.factorization 3)
  have hr_pos : 0 < r :=
    Nat.div_pos (Nat.le_of_dvd h₀ h23dvd)
      (Nat.mul_pos (pow_pos (by norm_num) _) (pow_pos (by norm_num) _))
  have hr_fact2 : r.factorization 2 = 0 := by
    rw [Nat.factorization_div h23dvd, Finsupp.tsub_apply,
      Nat.factorization_mul (pow_ne_zero _ (by norm_num)) (pow_ne_zero _ (by norm_num))]
    simp [Nat.factorization_pow]
    norm_num [Nat.Prime.factorization_self, Nat.Prime.factorization]
  have hr_fact3 : r.factorization 3 = 0 := by
    rw [Nat.factorization_div h23dvd, Finsupp.tsub_apply,
      Nat.factorization_mul (pow_ne_zero _ (by norm_num)) (pow_ne_zero _ (by norm_num))]
    simp [Nat.factorization_pow]
    norm_num [Nat.Prime.factorization_self, Nat.Prime.factorization]
  have hr_cop2 : Nat.Coprime r 2 := by
    rw [Nat.coprime_comm, Nat.Prime.coprime_iff_not_dvd Nat.prime_two]
    intro hdvd
    exact absurd
      ((Nat.Prime.dvd_iff_one_le_factorization Nat.prime_two hr_pos.ne').mp hdvd) (by omega)
  have hr_cop3 : Nat.Coprime r 3 := by
    rw [Nat.coprime_comm, Nat.Prime.coprime_iff_not_dvd Nat.prime_three]
    intro hdvd
    exact absurd
      ((Nat.Prime.dvd_iff_one_le_factorization Nat.prime_three hr_pos.ne').mp hdvd) (by omega)
  refine ⟨n.factorization 2, n.factorization 3, r, (Nat.mul_div_cancel' h23dvd).symm, ?_, hr_pos⟩
  rw [show (6 : ℕ) = 2 * 3 from rfl]
  exact hr_cop2.mul_right hr_cop3

end Problems.Minif2f.mathd_numbertheory_709
