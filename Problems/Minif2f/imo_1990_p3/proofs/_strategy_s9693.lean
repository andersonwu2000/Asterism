import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_gcd_two_n_p_sub_one_eq_two
import Problems.Minif2f.imo_1990_p3.proofs.L_two_pow_p_sub_one_eq_one_mod_p
import Problems.Minif2f.imo_1990_p3.proofs.L_two_pow_two_n_eq_one_mod_p

namespace Problems.Minif2f.imo_1990_p3

-- Decompose `(2:ZMod p)^2 = 1` via orderOf-divisibility: order of 2 divides
-- both `2*n` (from `p² ∣ 2^n+1`) and `p-1` (Fermat), hence divides their gcd.
-- Sub-goals: (1) `two_pow_two_n_eq_one_mod_p` — pow argument from `n²∣2^n+1`;
-- (2) `two_pow_p_sub_one_eq_one_mod_p` — Fermat; (3) `gcd_two_n_p_sub_one_eq_two`
-- — the heart: gcd(2n, p-1)=2 (the order-of-2 / 3-adic structure argument).
theorem s9693 :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 3 ∣ n → ¬ (9 ∣ n) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ n → (2 : ZMod p)^2 = 1 := by
  intro n hn hdvd h3 h9 p hp hge hpn
  have h_pow_2n : (2 : ZMod p) ^ (2 * n) = 1 :=
    two_pow_two_n_eq_one_mod_p n hn hdvd h3 h9 p hp hge hpn
  have h_pow_pm1 : (2 : ZMod p) ^ (p - 1) = 1 :=
    two_pow_p_sub_one_eq_one_mod_p n hn hdvd h3 h9 p hp hge hpn
  have h_gcd : Nat.gcd (2 * n) (p - 1) = 2 :=
    gcd_two_n_p_sub_one_eq_two n hn hdvd h3 h9 p hp hge hpn
  have hord : orderOf (2 : ZMod p) ∣ Nat.gcd (2 * n) (p - 1) :=
    Nat.dvd_gcd (orderOf_dvd_of_pow_eq_one h_pow_2n) (orderOf_dvd_of_pow_eq_one h_pow_pm1)
  rw [h_gcd] at hord
  exact orderOf_dvd_iff_pow_eq_one.mp hord
end Problems.Minif2f.imo_1990_p3
