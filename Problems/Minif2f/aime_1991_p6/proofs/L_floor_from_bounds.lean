import Mathlib
namespace Problems.Minif2f.aime_1991_p6

-- floor_from_bounds: Int.floor_eq_iff reduces ⌊100r⌋=743 to 743≤100r<744, closed by linarith from bounds
theorem floor_from_bounds :
    ∀ (r : ℝ), (743 : ℝ)/100 ≤ r ∧ r < 744/100 → Int.floor (100 * r) = 743 := by
  intro r ⟨h1, h2⟩
  rw [Int.floor_eq_iff]
  constructor
  · push_cast; linarith
  · push_cast; linarith

end Problems.Minif2f.aime_1991_p6
