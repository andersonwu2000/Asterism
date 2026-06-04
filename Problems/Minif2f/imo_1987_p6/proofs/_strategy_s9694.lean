import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs.L_every_prime_div_eq_self

namespace Problems.Minif2f.imo_1987_p6

-- Reduce primality of `n := i² + i + p` to: every prime divisor of `n`
-- equals `n`. The substantive IMO core argument (a prime divisor `q ≤ √n`
-- would force `k² + k + p = q` for some `k < i` by the strong IH, then a
-- size comparison contradicts `q ≤ √n < n`) is concentrated in the single
-- sub-goal `every_prime_div_eq_self`. The combinator is purely structural:
-- `Nat.minFac n` is a prime divisor, so if every prime divisor equals `n`,
-- then `minFac n = n`, which by `Nat.prime_def_minFac` gives `Nat.Prime n`.
theorem s9694 : ∀ (p : ℕ), Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.floor (Real.sqrt ((p:ℝ)/3)) < i →
    (∀ m < i, m ≤ p - 2 → Nat.Prime (m^2 + m + p)) →
    Nat.Prime (i^2 + i + p)  := by
  intro p hp hk i hi hlarge ih
  have hp2 : 2 ≤ p := hp.two_le
  have hn2 : 2 ≤ i^2 + i + p := by
    have : p ≤ i^2 + i + p := by linarith [Nat.zero_le (i^2 + i)]
    linarith
  have hdiv : ∀ q, q.Prime → q ∣ (i^2 + i + p) → q = i^2 + i + p :=
    every_prime_div_eq_self p hp hk i hi hlarge ih
  rw [Nat.prime_def_minFac]
  refine ⟨hn2, ?_⟩
  have hmin_prime : (i^2 + i + p).minFac.Prime := Nat.minFac_prime (by omega)
  have hmin_dvd : (i^2 + i + p).minFac ∣ (i^2 + i + p) := Nat.minFac_dvd _
  exact hdiv (i^2 + i + p).minFac hmin_prime hmin_dvd


end Problems.Minif2f.imo_1987_p6
