import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- min_fac_odd: 2^n+1 is odd, so n²∣2^n+1 forces n odd, hence minFac n > 2
theorem min_fac_odd : ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → 2 < Nat.minFac n := by
  intro n hn hdvd
  have hn_odd : ¬ 2 ∣ n := by
    intro h2n
    have h2n2 : 2 ∣ n ^ 2 := dvd_pow h2n two_ne_zero
    have h2 : 2 ∣ 2 ^ n + 1 := dvd_trans h2n2 hdvd
    have hmod : (2 ^ n + 1) % 2 = 1 := by
      have : 2 ^ n % 2 = 0 := by
        induction n with
        | zero => omega
        | succ k ih => simp [pow_succ]
      omega
    omega
  have hprime : (Nat.minFac n).Prime := Nat.minFac_prime (by omega)
  have hge2 := hprime.two_le
  have hne2 : Nat.minFac n ≠ 2 := fun heq => hn_odd (heq ▸ Nat.minFac_dvd n)
  omega

end Problems.Minif2f.imo_1990_p3
