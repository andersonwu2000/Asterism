import Mathlib
import Problems.Minif2f.amc12b_2002_p3.Defs

namespace Problems.Minif2f.amc12b_2002_p3

-- three_in_s: rw h₀ reduces to 0<3 ∧ Nat.Prime 2; norm_num closes both
theorem three_in_s (S : Finset ℕ)
    (h₀ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ Nat.Prime (n ^ 2 + 2 - 3 * n)) :
    (3 : ℕ) ∈ S := by rw [h₀]; norm_num

end Problems.Minif2f.amc12b_2002_p3
