import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_13

-- u_le_39: IsLeast.lb applied to 39 ∈ S (14*39%100=46, witnessed by norm_num).
theorem u_le_39 : ∀ (u v : ℕ) (S : Set ℕ)
    (_ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ 14 * n % 100 = 46)
    (_ : IsLeast S u) (_ : IsLeast (S \ {u}) v), u ≤ 39 := by
  intro u v S hS hu _
  apply hu.2
  rw [hS]
  norm_num

end Problems.Minif2f.mathd_numbertheory_13
