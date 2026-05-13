import Mathlib
import Problems.Minif2f.aime_1997_p11.Defs
import Problems.Minif2f.aime_1997_p11.proofs.L_floor_hundred_one_plus_sqrt_two
import Problems.Minif2f.aime_1997_p11.proofs.L_x_eq_one_plus_sqrt_two

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.aime_1997_p11

-- Reduce to closed form x = 1 + √2 then evaluate floor.
-- (1) trig telescoping: (Σ cos n°)/(Σ sin n°) = cot 22.5° = 1+√2.
-- (2) arithmetic: ⌊100·(1+√2)⌋ = 241 from 1.41 ≤ √2 < 1.42.
set_option linter.style.longLine false in
theorem s544 : ∀ (x : ℝ) (h₀ : x = (∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.cos (n * π / 180)) / ∑ n ∈ Finset.Icc (1 : ℕ) 44, Real.sin (n * π / 180)), Int.floor (100 * x) = 241  := by
  intro x h₀
  have h1 : x = 1 + Real.sqrt 2 := x_eq_one_plus_sqrt_two x h₀
  have h2 : Int.floor (100 * (1 + Real.sqrt 2)) = 241 := floor_hundred_one_plus_sqrt_two
  rw [h1]
  exact h2

end Problems.Minif2f.aime_1997_p11
