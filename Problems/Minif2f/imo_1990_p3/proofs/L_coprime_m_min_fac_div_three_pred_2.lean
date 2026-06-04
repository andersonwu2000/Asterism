import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- entry_kind: Backward
theorem coprime_m_min_fac_div_three_pred_2 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ≠ 7 → p ∣ m →
      Nat.Coprime m (Nat.minFac (m / 3) - 1) := by sorry

end Problems.Minif2f.imo_1990_p3
