import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs

namespace Problems.Minif2f.imo_1977_p5

-- abs_eq_28_of_sq_784: factor z²=784 as (z-28)(z+28)=0, then abs from each root
theorem abs_eq_28_of_sq_784 : ∀ (z : ℤ), z ^ 2 = 784 → |z| = 28 := by
  intro z hz
  have h2 : (z - 28) * (z + 28) = 0 := by ring_nf; linarith
  rcases mul_eq_zero.mp h2 with h | h
  · have : z = 28 := by linarith
    simp [this]
  · have : z = -28 := by linarith
    simp [this]

end Problems.Minif2f.imo_1977_p5
