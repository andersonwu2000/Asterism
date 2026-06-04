import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs.L_lower_bound
import Problems.Minif2f.imo_1987_p6.proofs.L_upper_bound

namespace Problems.Minif2f.imo_1987_p6

-- Split the conjunction into two independent bounds:
-- (1) lower_bound — `i < r`: if r ≤ i, then j := i mod r < i, r ∣ j²+j+p, IH gives
--     Nat.Prime (j²+j+p), forcing r = j²+j+p ≥ p ≥ r+2, contradiction.
-- (2) upper_bound — `r ≤ 2*i`: size analysis. If r > 2i then (2i+1)² ≤ r² ≤ i²+i+p
--     ⇒ 3i²+3i+1 ≤ p ⇒ i² < p/3, contradicting ⌊√(p/3)⌋ < i.
theorem s9808 : ∀ (p : ℕ), Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.floor (Real.sqrt ((p:ℝ)/3)) < i →
    (∀ m < i, m ≤ p - 2 → Nat.Prime (m^2 + m + p)) →
    ∀ r, r.Prime → r ∣ (i^2 + i + p) → r^2 ≤ i^2 + i + p →
    i < r ∧ r ≤ 2 * i  := by
  intro p hp hbase i hi hfloor hih r hr hrdvd hr2
  have h_lb : i < r := lower_bound p hp hbase i hi hfloor hih r hr hrdvd hr2
  have h_ub : r ≤ 2 * i := upper_bound p hp hbase i hi hfloor hih r hr hrdvd hr2
  exact ⟨h_lb, h_ub⟩

end Problems.Minif2f.imo_1987_p6
