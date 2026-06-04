import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs.L_no_small_prime_factor

namespace Problems.Minif2f.imo_1987_p6

-- Reduce "every prime divisor of n = i²+i+p equals n" to "no prime divisor q
-- satisfies q² ≤ n". The substantive IMO core argument (find k ≤ (q-1)/2
-- with q | f(k), use IH to get q = k²+k+p, then derive p² ≤ p²-2p+2) is
-- concentrated in `no_small_prime_factor`. The combinator is purely
-- structural: minFac n is a prime divisor, sub-goal forces (minFac n)² > n,
-- so by Nat.minFac_le_div contrapositive n is prime, hence q = n.
theorem s9735 : ∀ (p : ℕ), Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.floor (Real.sqrt ((p:ℝ)/3)) < i →
    (∀ m < i, m ≤ p - 2 → Nat.Prime (m^2 + m + p)) →
    ∀ q, q.Prime → q ∣ (i^2 + i + p) → q = i^2 + i + p  := by
  intro p hp hbase i hi hi_gt hih q hq hdvd
  have hpge2 : 2 ≤ p := hp.two_le
  have hnge2 : 2 ≤ i^2 + i + p := by
    have : p ≤ i^2 + i + p := by linarith [Nat.zero_le (i^2 + i)]
    linarith
  have hsmall : ∀ r, r.Prime → r ∣ (i^2 + i + p) → r^2 ≤ i^2 + i + p → False :=
    no_small_prime_factor p hp hbase i hi hi_gt hih

  set n := i^2 + i + p with hn_def

  have hm_prime : n.minFac.Prime := Nat.minFac_prime (by omega)
  have hm_dvd : n.minFac ∣ n := Nat.minFac_dvd _
  have hm_sq_gt : n < n.minFac ^ 2 := by
    by_contra h
    push_neg at h
    exact hsmall n.minFac hm_prime hm_dvd h
  have hn_prime : n.Prime := by
    rw [Nat.prime_def_minFac]
    refine ⟨hnge2, ?_⟩
    by_contra hne
    have hle : n.minFac ≤ n / n.minFac := by
      apply Nat.minFac_le_div (by omega)
      rw [Nat.prime_def_minFac]
      push_neg
      intro _
      exact hne
    have hmul : n.minFac * n.minFac ≤ n := by
      calc n.minFac * n.minFac ≤ (n / n.minFac) * n.minFac := Nat.mul_le_mul_right _ hle
        _ = n := Nat.div_mul_cancel hm_dvd
    have : n.minFac ^ 2 ≤ n := by rw [pow_two]; exact hmul
    omega
  exact (hn_prime.eq_one_or_self_of_dvd q hdvd).resolve_left hq.one_lt.ne'

end Problems.Minif2f.imo_1987_p6
