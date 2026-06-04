import Mathlib
import Problems.Minif2f.aimeII_2020_p6.Defs
import Problems.Minif2f.aimeII_2020_p6.proofs.L_t_2020_eq

namespace Problems.Minif2f.aimeII_2020_p6

-- Reduce to: t 2020 = 101 / 525 (periodicity-5 of the recurrence).
-- Once that value is established, the final identity ↑den + num = 626 is a
-- numeric check on the rational literal 101/525 closed by `norm_num`.
theorem s765 : ∀ (t : ℕ → ℚ) (h₀ : t 1 = 20) (h₁ : t 2 = 21)
    (h₂ : ∀ n ≥ 3, t n = (5 * t (n - 1) + 1) / (25 * t (n - 2))),
    ↑(t 2020).den + (t 2020).num = 626 := by
  intro t h₀ h₁ h₂
  have h_t2020 : t 2020 = 101 / 525 := t_2020_eq t h₀ h₁ h₂
  rw [h_t2020]
  norm_num

end Problems.Minif2f.aimeII_2020_p6
