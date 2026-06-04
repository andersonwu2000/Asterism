import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_decompose_n_two_three_coprime
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_tau_coprime_part_eq_one

namespace Problems.Minif2f.mathd_numbertheory_709

-- Two-step decomp:
-- A. `decompose_n_two_three_coprime`: pure-arithmetic split — any n>0 factors as 2^a * 3^b * r
--    with Coprime r 6 (take a := n.factorization 2, b := n.factorization 3, r := remaining).
-- B. `tau_coprime_part_eq_one`: τ(2n)=28 ∧ τ(3n)=30 forces that 6-coprime part r = 1
--    (the τ analysis: (a+2)(b+1)τ(r)=28, (a+1)(b+2)τ(r)=30 ⇒ τ(r)=1 ⇒ r=1).
-- Combinator: substitute n = 2^a * 3^b in m ∣ n; m coprime to 6 ⇒ coprime to 2^a;
-- so m ∣ 3^b; then m = gcd(m, 3^b) = 1.
theorem s9835 :
    ∀ (n : ℕ) (h₀ : 0 < n)
      (h₁ : Finset.card (Nat.divisors (2 * n)) = 28)
      (h₂ : Finset.card (Nat.divisors (3 * n)) = 30),
      ∀ m, m ∣ n → Nat.Coprime m 6 → m = 1 := by
  intro n h₀ h₁ h₂ m hm hcop
  have h_decomp := decompose_n_two_three_coprime n h₀ h₁ h₂
  obtain ⟨a, b, r, hn, hrcop, hrpos⟩ := h_decomp
  have hreq : r = 1 := tau_coprime_part_eq_one n h₀ h₁ h₂ a b r hn hrcop hrpos
  rw [hreq, Nat.mul_one] at hn
  rw [hn] at hm
  have hcop2 : Nat.Coprime m 2 := hcop.coprime_dvd_right (by norm_num)
  have hcop3 : Nat.Coprime m 3 := hcop.coprime_dvd_right (by norm_num)
  have hcop2a : Nat.Coprime m (2 ^ a) := hcop2.pow_right a
  have hdvd3 : m ∣ 3 ^ b := hcop2a.dvd_of_dvd_mul_left hm
  have hcop3b : Nat.Coprime m (3 ^ b) := hcop3.pow_right b
  have hm_dvd_gcd : m ∣ Nat.gcd m (3 ^ b) := Nat.dvd_gcd dvd_rfl hdvd3
  have hm_eq : m = Nat.gcd m (3 ^ b) := Nat.dvd_antisymm hm_dvd_gcd (Nat.gcd_dvd_left m (3 ^ b))
  rw [hm_eq]
  exact hcop3b

end Problems.Minif2f.mathd_numbertheory_709
