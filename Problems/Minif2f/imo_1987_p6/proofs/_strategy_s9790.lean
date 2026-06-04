import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs.L_bounds_r
import Problems.Minif2f.imo_1987_p6.proofs.L_div_witness

namespace Problems.Minif2f.imo_1987_p6

-- Schur trick: build witness k := r - 1 - i. Two bounds (i < r ≤ 2i) come from
-- size analysis (degenerate case ruled out by ⌊√(p/3)⌋ < i); divisibility comes
-- from algebraic identity (r-1-i ≡ -1-i mod r ⇒ (r-1-i)²+(r-1-i)+p ≡ i²+i+p).
theorem s9790 : ∀ (p : ℕ), Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.floor (Real.sqrt ((p:ℝ)/3)) < i →
    (∀ m < i, m ≤ p - 2 → Nat.Prime (m^2 + m + p)) →
    ∀ r, r.Prime → r ∣ (i^2 + i + p) → r^2 ≤ i^2 + i + p →
    ∃ k, k < i ∧ k ≤ p - 2 ∧ r ∣ (k^2 + k + p)  := by
  intro p hp hbase i hi hfloor hIH r hr hrdvd hr2
  have hbnd : i < r ∧ r ≤ 2 * i := bounds_r p hp hbase i hi hfloor hIH r hr hrdvd hr2
  have hdvd : r ∣ ((r - 1 - i)^2 + (r - 1 - i) + p) :=
    div_witness p hp hbase i hi hfloor hIH r hr hrdvd hr2 hbnd.1 hbnd.2
  refine ⟨r - 1 - i, ?_, ?_, hdvd⟩
  · omega
  · omega
end Problems.Minif2f.imo_1987_p6
