import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_min_fac_div_three_prime_ge_five
import Problems.Minif2f.imo_1990_p3.proofs.L_two_sq_eq_one_min_fac_div_three

namespace Problems.Minif2f.imo_1990_p3

-- Pivot to q := Nat.minFac (m/3) (smallest prime factor of m above 3) instead of arbitrary p.
-- Two sub-goals: (1) q is prime ≥ 5; (2) (2:ZMod q)^2 = 1 (the hard lemma — uses minimality
-- of q and ¬7∣m to collapse the order argument).  Closer: (2:ZMod q)^2 = 1 forces 3=0 in
-- ZMod q, so q ∣ 3, contradicting q ≥ 5.
theorem s9853 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m → False  := by
  intro m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  have h_prime_ge :=
    min_fac_div_three_prime_ge_five m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  have h_two_sq :=
    two_sq_eq_one_min_fac_div_three m hm hpow h3 h9 h7 p hp h5 hp7 hpm
  set q := Nat.minFac (m / 3) with hq_def
  have h3z : (3 : ZMod q) = 0 := by linear_combination h_two_sq
  have hcast : ((3 : ℕ) : ZMod q) = 0 := by exact_mod_cast h3z
  have hdvd3 : q ∣ 3 := (CharP.cast_eq_zero_iff (ZMod q) q 3).mp hcast
  have hle : q ≤ 3 := Nat.le_of_dvd (by norm_num) hdvd3
  linarith [h_prime_ge.2]

end Problems.Minif2f.imo_1990_p3
