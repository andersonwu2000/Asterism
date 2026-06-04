import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs

namespace Problems.Minif2f.imo_1987_p6

-- mod_dvd_witness: if r ∣ i²+i+p then r ∣ (i%r)²+(i%r)+p, via Nat.ModEq congruence
-- i ≡ i%r [MOD r], so i²+i+p ≡ (i%r)²+(i%r)+p [MOD r]; divisibility transfers.
theorem mod_dvd_witness : ∀ (p : ℕ), Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.floor (Real.sqrt ((p:ℝ)/3)) < i →
    (∀ m < i, m ≤ p - 2 → Nat.Prime (m^2 + m + p)) →
    ∀ r, r.Prime → r ∣ (i^2 + i + p) → r^2 ≤ i^2 + i + p →
    r ∣ ((i % r)^2 + (i % r) + p) := by
  intro p hp hbase i hi hfloor IH r hr hdvd hle
  have hcong : i ≡ i % r [MOD r] := by
    simp [Nat.ModEq, Nat.mod_mod_of_dvd]
  have hcong2 : i^2 + i + p ≡ (i % r)^2 + (i % r) + p [MOD r] := by
    apply Nat.ModEq.add_right
    apply Nat.ModEq.add
    · exact hcong.pow 2
    · exact hcong
  exact (Nat.modEq_zero_iff_dvd.mp (Nat.ModEq.trans (Nat.ModEq.symm hcong2)
    (Nat.modEq_zero_iff_dvd.mpr hdvd)))

end Problems.Minif2f.imo_1987_p6
