import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs

namespace Problems.Minif2f.mathd_numbertheory_709

-- card_coprime_6_pow_two_pow_three_le_one: any divisor of 2^a*3^b coprime to 6 must be 1,
-- since coprimality to 6 forces coprimality to each prime-power factor, then
-- Nat.gcd_eq_left (dvd) collapses with Nat.Coprime to give d = 1.
theorem card_coprime_6_pow_two_pow_three_le_one : ∀ a b : ℕ,
    ((Nat.divisors (2 ^ a * 3 ^ b)).filter (fun d => Nat.Coprime d 6)).card ≤ 1 := by
  intro a b
  rw [Finset.card_le_one]
  intro x hx y hy
  simp only [Finset.mem_filter, Nat.mem_divisors] at hx hy
  obtain ⟨⟨hxdvd, _⟩, hxcop⟩ := hx
  obtain ⟨⟨hydvd, _⟩, hycop⟩ := hy
  have aux : ∀ d : ℕ, d ∣ 2 ^ a * 3 ^ b → Nat.Coprime d 6 → d = 1 := by
    intro d hdvd hcop
    have h2 : Nat.Coprime d 2 := Nat.Coprime.coprime_dvd_right (by norm_num) hcop
    have h3 : Nat.Coprime d 3 := Nat.Coprime.coprime_dvd_right (by norm_num) hcop
    have hd2a : Nat.Coprime d (2 ^ a) := h2.pow_right a
    have hd3b : Nat.Coprime d (3 ^ b) := h3.pow_right b
    have hdcop : Nat.Coprime d (2 ^ a * 3 ^ b) := hd2a.mul_right hd3b
    have hgcd : Nat.gcd d (2 ^ a * 3 ^ b) = d := Nat.gcd_eq_left hdvd
    have hceq : Nat.gcd d (2 ^ a * 3 ^ b) = 1 := hdcop
    exact hgcd.symm.trans hceq
  exact (aux x hxdvd hxcop).trans (aux y hydvd hycop).symm

end Problems.Minif2f.mathd_numbertheory_709
