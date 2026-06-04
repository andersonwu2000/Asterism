import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_three_lte_lifting

namespace Problems.Minif2f.imo_1990_p3

-- Reduce LTE-style lower bound to a clean k,m-parametrized lifting helper:
-- write n = 3^k * m where k = v_3(n) and m = ord_compl[3] n is odd & 3-coprime,
-- then the helper proves 3^(k+1) ∣ 2^(3^k*m)+1 by induction on k.
theorem s9728 :
    ∀ (n : ℕ), 2 ≤ n → Odd n → 3 ∣ n →
      3 ^ (1 + n.factorization 3) ∣ (2 ^ n + 1)  := by
  intro n hn hodd h3
  have hn_ne : n ≠ 0 := by omega
  set k := n.factorization 3 with hk_def
  set m := n / 3 ^ k with hm_def
  have hkm : 3 ^ k * m = n := Nat.ordProj_mul_ordCompl_eq_self n 3
  have hm_not3 : ¬ (3 ∣ m) := Nat.not_dvd_ordCompl Nat.prime_three hn_ne
  have hm_odd : Odd m := by
    have hodd' : Odd (3 ^ k * m) := by rw [hkm]; exact hodd
    exact Nat.Odd.of_mul_right hodd'
  have hkey : 3 ^ (k + 1) ∣ 2 ^ (3 ^ k * m) + 1 :=
    three_lte_lifting k m hm_odd hm_not3
  rw [hkm] at hkey
  rw [show 1 + k = k + 1 from Nat.add_comm 1 k]
  exact hkey

end Problems.Minif2f.imo_1990_p3
