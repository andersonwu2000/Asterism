import Mathlib
import Problems.Minif2f.mathd_numbertheory_13.Defs

namespace Problems.Minif2f.mathd_numbertheory_13

-- Direct: 89 ∈ S (since 14*89 % 100 = 46) and u ≤ 39 < 89 (since 39 ∈ S),
-- so 89 ∈ S \ {u}, and the lower-bound property of v on S \ {u} gives v ≤ 89.
theorem s9344 : ∀ (u v : ℕ) (S : Set ℕ) (_ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ 14 * n % 100 = 46) (_ : IsLeast S u) (_ : IsLeast (S \ {u}) v), v ≤ 89  := by
  intro u v S hS huLeast hvLeast
  have h89_in_S : 89 ∈ S := (hS 89).mpr ⟨by norm_num, by norm_num⟩
  have h39_in_S : 39 ∈ S := (hS 39).mpr ⟨by norm_num, by norm_num⟩
  have hu_le_39 : u ≤ 39 := huLeast.2 h39_in_S
  have hu_ne_89 : u ≠ 89 := by omega
  have h89_in_diff : 89 ∈ S \ {u} := ⟨h89_in_S, fun h => hu_ne_89 h.symm⟩
  exact hvLeast.2 h89_in_diff

end Problems.Minif2f.mathd_numbertheory_13
