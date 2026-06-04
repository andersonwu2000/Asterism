import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs

namespace Problems.Minif2f.imo_1987_p6

-- size_clash_helper: prime divisor r of i²+i+p with r²≤i²+i+p cannot divide any prime k²+k+p,
-- since r=k²+k+p≥p but r²≤(p-2)²+(p-2)+p<p², contradiction via nlinarith.
theorem size_clash_helper : ∀ (p : ℕ), Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.floor (Real.sqrt ((p:ℝ)/3)) < i →
    (∀ m < i, m ≤ p - 2 → Nat.Prime (m^2 + m + p)) →
    ∀ r, r.Prime → r ∣ (i^2 + i + p) → r^2 ≤ i^2 + i + p →
    ∀ k, r ∣ (k^2 + k + p) → Nat.Prime (k^2 + k + p) → False := by
  intro p hp _hbase i hi _hfloor _hIH r hr _hrdvd hr2 k hrkdvd hkprime
  have hr_eq : r = k ^ 2 + k + p := by
    rcases hkprime.eq_one_or_self_of_dvd r hrkdvd with h | h
    · exact absurd h hr.one_lt.ne'
    · exact h
  have hpr : p ≤ r := hr_eq ▸ Nat.le_add_left p (k ^ 2 + k)
  have hp2r2 : p ^ 2 ≤ r ^ 2 := Nat.pow_le_pow_left hpr 2
  have h4 : p ^ 2 ≤ i ^ 2 + i + p := le_trans hp2r2 hr2
  have hp2 : 2 ≤ p := hp.two_le
  have hip : i + 2 ≤ p := by omega
  obtain ⟨d, hd⟩ := Nat.exists_eq_add_of_le hip
  nlinarith [Nat.zero_le d, Nat.zero_le i, sq_nonneg d,
             mul_nonneg (Nat.zero_le d) (Nat.zero_le i)]

end Problems.Minif2f.imo_1987_p6
