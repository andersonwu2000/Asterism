import Mathlib
namespace Problems.Minif2f.amc12a_2008_p8

-- cube_eq_two_sqrt_two: Real.sqrt_sq identifies x = √2 from x>0, x²=2; then calc finishes
theorem cube_eq_two_sqrt_two : ∀ (x : ℝ), 0 < x → x ^ 2 = 2 →
    x ^ 3 = 2 * Real.sqrt 2 := by
  intro x hx hx2
  have hx_eq : x = Real.sqrt 2 := by
    have h := Real.sqrt_sq hx.le
    rw [hx2] at h
    exact h.symm
  calc x ^ 3 = x ^ 2 * x := by ring
    _ = 2 * x := by rw [hx2]
    _ = 2 * Real.sqrt 2 := by rw [hx_eq]

end Problems.Minif2f.amc12a_2008_p8
