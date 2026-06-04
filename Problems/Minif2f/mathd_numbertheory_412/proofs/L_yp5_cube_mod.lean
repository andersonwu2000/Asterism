import Mathlib
namespace Problems.Minif2f.mathd_numbertheory_412

-- yp5_cube_mod: Int.ModEq.pow lifts y+5 ≡ 12 [ZMOD 19] to the cube, then omega closes.
theorem yp5_cube_mod : ∀ (y : ℤ), y % 19 = 7 → (y + 5) ^ 3 % 19 = 18 := by
  intro y hy
  have h1 : y + 5 ≡ 12 [ZMOD 19] := by
    simp [Int.ModEq]
    omega
  have h2 : (y + 5) ^ 3 ≡ 12 ^ 3 [ZMOD 19] := h1.pow 3
  simp [Int.ModEq] at h2
  omega

end Problems.Minif2f.mathd_numbertheory_412
