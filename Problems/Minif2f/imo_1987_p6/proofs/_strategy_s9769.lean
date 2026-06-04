import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs
import Problems.Minif2f.imo_1987_p6.proofs.L_exists_small_witness
import Problems.Minif2f.imo_1987_p6.proofs.L_size_contradiction

namespace Problems.Minif2f.imo_1987_p6

-- Schur's argument for IMO 1987 P6 sub-goal: if r prime, r ∣ f(i), r² ≤ f(i),
-- find k < i (k ≤ p-2) with r ∣ f(k); base/IH gives f(k) prime; size yields ⊥.
-- Sub-goals: (1) `exists_small_witness` — the modular Schur trick (find k < i, k ≤ p-2
-- with r ∣ k²+k+p); (2) `size_contradiction` — given r ∣ f(k) and Nat.Prime f(k),
-- conclude ⊥ from r² ≤ f(i) and f(k) ≥ p (so r = f(k) ≥ p, but r² ≤ (p-2)²+(p-2)+p
-- < p², so r < p). Combinator dispatches base vs IH on whether k ≤ ⌊√(p/3)⌋.
theorem s9769 : ∀ (p : ℕ), Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.floor (Real.sqrt ((p:ℝ)/3)) < i →
    (∀ m < i, m ≤ p - 2 → Nat.Prime (m^2 + m + p)) →
    ∀ r, r.Prime → r ∣ (i^2 + i + p) → r^2 ≤ i^2 + i + p → False  := by
  intro p hp hbase i hi hi_gt hih r hr hr_dvd hr_sq
  have h_exists := exists_small_witness p hp hbase i hi hi_gt hih r hr hr_dvd hr_sq
  have h_size := size_contradiction p hp hbase i hi hi_gt hih r hr hr_dvd hr_sq
  obtain ⟨k, hk_lt, hk_le, hk_dvd⟩ := h_exists
  have hfk_prime : Nat.Prime (k^2 + k + p) := by
    by_cases hk_sqrt : k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3))
    · exact hbase k hk_sqrt
    · exact hih k hk_lt hk_le
  exact h_size k hk_dvd hfk_prime

end Problems.Minif2f.imo_1987_p6
