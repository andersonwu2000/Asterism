import Mathlib
namespace Problems.Minif2f.imo_1990_p3

-- cube_factor: ℕ identity a³+1 = (a+1)·(a²−a+1) via zify + ring
-- nlinarith supplies the side-condition a ≤ a² (needed for zify to handle
-- truncated subtraction), then ring closes after casting to ℤ.
theorem cube_factor : ∀ (a : ℕ), 1 ≤ a → a^3 + 1 = (a + 1) * (a^2 - a + 1) := by
  intro a ha
  have h : a ≤ a^2 := by nlinarith
  zify [h]
  ring

end Problems.Minif2f.imo_1990_p3
