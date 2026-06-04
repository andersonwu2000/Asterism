import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs.L_mod_dvd_witness
import Problems.Minif2f.imo_1987_p6.proofs.L_size_clash_helper

namespace Problems.Minif2f.imo_1987_p6

-- Decompose `i < r` by contradiction: assume r ≤ i; take j := i mod r < r ≤ i.
-- Sub-goal `mod_dvd_witness` lifts r ∣ (i²+i+p) to r ∣ (j²+j+p) via congruence.
-- Sub-goal `size_clash_helper` packages the size argument (r prime divisor of a
-- prime number forces r = j²+j+p ≥ p, but r² ≤ i²+i+p ≤ (p-2)²+(p-2)+p < p²).
-- IH closes Nat.Prime (j²+j+p) from j < i ≤ p-2.
theorem s9823 : ∀ (p : ℕ), Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.floor (Real.sqrt ((p:ℝ)/3)) < i →
    (∀ m < i, m ≤ p - 2 → Nat.Prime (m^2 + m + p)) →
    ∀ r, r.Prime → r ∣ (i^2 + i + p) → r^2 ≤ i^2 + i + p →
    i < r := by
  intro p hp hbase i hi hfloor hIH r hr hrdvd hr2
  by_contra hcon
  push Not at hcon
  have h_mod_dvd := mod_dvd_witness p hp hbase i hi hfloor hIH r hr hrdvd hr2
  have hr_pos : 0 < r := hr.pos
  have hj_lt_r : i % r < r := Nat.mod_lt i hr_pos
  have hj_lt_i : i % r < i := lt_of_lt_of_le hj_lt_r hcon
  have hj_le : i % r ≤ p - 2 := le_trans hj_lt_i.le hi
  have hjprime : Nat.Prime ((i % r)^2 + (i % r) + p) := hIH (i % r) hj_lt_i hj_le
  have h_size_clash := size_clash_helper p hp hbase i hi hfloor hIH r hr hrdvd hr2
  exact h_size_clash (i % r) h_mod_dvd hjprime

end Problems.Minif2f.imo_1987_p6
