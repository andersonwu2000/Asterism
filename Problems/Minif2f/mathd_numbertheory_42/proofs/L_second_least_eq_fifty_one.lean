import Mathlib
import Problems.Minif2f.mathd_numbertheory_42.Defs

namespace Problems.Minif2f.mathd_numbertheory_42

-- second_least_eq_fifty_one: IsLeast + interval_cases to pin u=11 then v=51
-- S = {a : ℕ | 0 < a ∧ 27*a % 40 = 17} = {11, 51, 91, ...}; least is 11, second-least is 51.
theorem second_least_eq_fifty_one (S : Set ℕ) (u v : ℕ)
    (h₀ : ∀ a : ℕ, a ∈ S ↔ 0 < a ∧ 27 * a % 40 = 17)
    (h₁ : IsLeast S u) (h₂ : IsLeast (S \ {u}) v) : v = 51 := by
  have h11 : (11 : ℕ) ∈ S := (h₀ 11).mpr (by norm_num)
  have h51 : (51 : ℕ) ∈ S := (h₀ 51).mpr (by norm_num)
  have hu11 : u ≤ 11 := h₁.2 h11
  have huS := h₁.1
  have hupos : 0 < u := ((h₀ u).mp huS).1
  have humod : 27 * u % 40 = 17 := ((h₀ u).mp huS).2
  have hu_eq : u = 11 := by interval_cases u <;> omega
  subst hu_eq
  have h51S : (51 : ℕ) ∈ S \ {11} := ⟨h51, by simp⟩
  have hv51 : v ≤ 51 := h₂.2 h51S
  have hvS := h₂.1
  have hvmem : v ∈ S := hvS.1
  have hvne : v ≠ 11 := by
    intro heq; subst heq; exact hvS.2 (Set.mem_singleton 11)
  have hvpos : 0 < v := ((h₀ v).mp hvmem).1
  have hvmod : 27 * v % 40 = 17 := ((h₀ v).mp hvmem).2
  interval_cases v <;> omega

end Problems.Minif2f.mathd_numbertheory_42
