import Mathlib
import Problems.Minif2f.mathd_numbertheory_13.Defs

namespace Problems.Minif2f.mathd_numbertheory_13

-- Direct leaf: from `u ∈ S` extract `0 < u ∧ 14*u%100 = 46`; `omega` handles the
-- mod-50 residue argument (the smallest positive n with 14n%100=46 is n=39).
theorem s9476 : ∀ (u v : ℕ) (S : Set ℕ) (_ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ 14 * n % 100 = 46) (_ : IsLeast S u) (_ : IsLeast (S \ {u}) v), 39 ≤ u  := by
  intro u v S hS hu _
  have hu_mem : u ∈ S := hu.1
  rw [hS] at hu_mem
  omega

end Problems.Minif2f.mathd_numbertheory_13
