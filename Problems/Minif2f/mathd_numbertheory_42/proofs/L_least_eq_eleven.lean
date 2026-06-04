import Mathlib
import Problems.Minif2f.mathd_numbertheory_42.Defs

namespace Problems.Minif2f.mathd_numbertheory_42

-- least_eq_eleven: IsLeast + modular membership — 11 is smallest positive a with 27*a%40=17
theorem least_eq_eleven (S : Set ℕ) (u v : ℕ)
    (h₀ : ∀ a : ℕ, a ∈ S ↔ 0 < a ∧ 27 * a % 40 = 17)
    (h₁ : IsLeast S u) (h₂ : IsLeast (S \ {u}) v) : u = 11 := by
  have h11 : 11 ∈ S := by rw [h₀]; norm_num
  have hu_le : u ≤ 11 := h₁.2 h11
  have hu_mem := (h₀ u).mp h₁.1
  omega

end Problems.Minif2f.mathd_numbertheory_42
