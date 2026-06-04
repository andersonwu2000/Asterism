import Mathlib
import Problems.Minif2f.imo_1987_p6.Defs

namespace Problems.Minif2f.imo_1987_p6

-- div_witness: algebraic identity (r-1-i)²+(r-1-i)+p ≡ i²+i+p (mod r), lift to ℤ
theorem div_witness : ∀ (p : ℕ), Nat.Prime p →
    (∀ k ≤ Nat.floor (Real.sqrt ((p:ℝ)/3)), Nat.Prime (k^2 + k + p)) →
    ∀ i ≤ p - 2, Nat.floor (Real.sqrt ((p:ℝ)/3)) < i →
    (∀ m < i, m ≤ p - 2 → Nat.Prime (m^2 + m + p)) →
    ∀ r, r.Prime → r ∣ (i^2 + i + p) → r^2 ≤ i^2 + i + p →
    i < r → r ≤ 2 * i →
    r ∣ ((r - 1 - i)^2 + (r - 1 - i) + p) := by
  intro p _hp _hk i _hi _hi_floor _ihm r _hr hdvd _hr2 hir _hr2i
  have h1 : i + 1 ≤ r := hir
  zify [h1] at hdvd ⊢
  have hcast : (↑(r - 1 - i) : ℤ) = ↑r - 1 - ↑i := by omega
  rw [hcast]
  have identity : ((r : ℤ) - 1 - i) ^ 2 + ((r : ℤ) - 1 - i) + p =
      (↑i ^ 2 + ↑i + ↑p) + ↑r * (↑r - 1 - 2 * ↑i) := by ring
  rw [identity]
  exact dvd_add hdvd (dvd_mul_right _ _)

end Problems.Minif2f.imo_1987_p6
