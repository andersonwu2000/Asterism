import Mathlib
namespace Problems.Minif2f.imo_1990_p3

-- coprime_n_min_fac_pred: gcd(n, minFac(n)-1) = 1 via prime-factor contradiction
-- Any prime q | gcd must satisfy q ≥ minFac(n) (since q | n) and q ≤ minFac(n)-1
-- (since q | minFac(n)-1); contradiction from minFac minimality alone.
theorem coprime_n_min_fac_pred :
    ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → Nat.Coprime n (Nat.minFac n - 1) := by
  intro n hn _
  unfold Nat.Coprime
  by_contra h
  have hge2 : 2 ≤ Nat.gcd n (Nat.minFac n - 1) := by
    have hpos : 0 < Nat.gcd n (Nat.minFac n - 1) := by
      have hdvd : Nat.gcd n (Nat.minFac n - 1) ∣ n := Nat.gcd_dvd_left _ _
      exact Nat.pos_of_dvd_of_pos hdvd (by omega)
    omega
  set d := Nat.gcd n (Nat.minFac n - 1) with hd_def
  have hq_prime : (Nat.minFac d).Prime := Nat.minFac_prime (by omega)
  have hq_ge2 : 2 ≤ Nat.minFac d := hq_prime.two_le
  have hqn : Nat.minFac d ∣ n := (Nat.minFac_dvd d).trans (Nat.gcd_dvd_left n _)
  have hqpm1 : Nat.minFac d ∣ Nat.minFac n - 1 :=
    (Nat.minFac_dvd d).trans (Nat.gcd_dvd_right n _)
  have hp_prime : (Nat.minFac n).Prime := Nat.minFac_prime (by omega)
  have hp_ge2 : 2 ≤ Nat.minFac n := hp_prime.two_le
  have hpq : Nat.minFac n ≤ Nat.minFac d := Nat.minFac_le_of_dvd hq_ge2 hqn
  have hqle : Nat.minFac d ≤ Nat.minFac n - 1 :=
    Nat.le_of_dvd (by omega) hqpm1
  omega

end Problems.Minif2f.imo_1990_p3
