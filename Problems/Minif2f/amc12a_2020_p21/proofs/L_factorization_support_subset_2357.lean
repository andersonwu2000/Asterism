import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- factorization_support_subset_2357: primeFactors_mono + prime-tower decomposition of 5*10!
-- Uses Nat.primeFactors_mono for m ∣ 5*10!, then peels 2^8*(3^4*(5^3*7)) via
-- repeated Nat.Prime.dvd_mul + dvd_of_dvd_pow + eq_one_or_self_of_dvd. No native_decide.
theorem factorization_support_subset_2357 :
    ∀ m : ℕ, (5 ∣ m ∧ Nat.lcm 5! m = 5 * Nat.gcd 10! m) → m ∣ 5 * 10! →
      m.factorization.support ⊆ ({2, 3, 5, 7} : Finset ℕ) := by
  intro m _ hdvd
  have hm : m ≠ 0 := fun h => by subst h; norm_num at hdvd
  apply (Nat.primeFactors_mono hdvd (by norm_num)).trans
  intro p hp
  rw [Nat.mem_primeFactors] at hp
  obtain ⟨hprime, hpdvd, _⟩ := hp
  have hfact : (5 : ℕ) * 10 ! = 2 ^ 8 * 3 ^ 4 * 5 ^ 3 * 7 := by norm_num [Nat.factorial]
  rw [hfact] at hpdvd
  have hpdvd2 : p ∣ 2 ^ 8 * (3 ^ 4 * (5 ^ 3 * 7)) := by
    rwa [show (2 : ℕ) ^ 8 * (3 ^ 4 * (5 ^ 3 * 7)) = 2 ^ 8 * 3 ^ 4 * 5 ^ 3 * 7 from by ring]
  simp only [Finset.mem_insert, Finset.mem_singleton]
  rcases hprime.dvd_mul.mp hpdvd2 with h | h
  · exact Or.inl ((Nat.Prime.eq_one_or_self_of_dvd (by norm_num) p
        (hprime.dvd_of_dvd_pow h)).resolve_left hprime.one_lt.ne')
  · rcases hprime.dvd_mul.mp h with h | h
    · exact Or.inr (Or.inl ((Nat.Prime.eq_one_or_self_of_dvd (by norm_num) p
          (hprime.dvd_of_dvd_pow h)).resolve_left hprime.one_lt.ne'))
    · rcases hprime.dvd_mul.mp h with h | h
      · exact Or.inr (Or.inr (Or.inl ((Nat.Prime.eq_one_or_self_of_dvd (by norm_num) p
            (hprime.dvd_of_dvd_pow h)).resolve_left hprime.one_lt.ne')))
      · exact Or.inr (Or.inr (Or.inr ((Nat.Prime.eq_one_or_self_of_dvd (by norm_num) p
            h).resolve_left hprime.one_lt.ne')))

end Problems.Minif2f.amc12a_2020_p21
