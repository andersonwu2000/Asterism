import Mathlib
import Problems.Minif2f.imo_1961_p1.Defs

namespace Problems.Minif2f.imo_1961_p1

-- Direct proof: three independent inequalities from `0 < x, y, z` and pairwise-distinct.
-- (1) `0 < a` from positivity of `x + y + z = a` via `linarith`.
-- (2) `b^2 < a^2` since `a^2 - b^2 = 2(xy + yz + zx) > 0` (each cross term positive).
-- (3) `a^2 < 3 b^2` since `3 b^2 - a^2 = (x-y)^2 + (y-z)^2 + (z-x)^2 > 0`
--     (each square strictly positive from `x ≠ y, y ≠ z, z ≠ x`).
-- Hypothesis `h₆ : x * y = z^2` is unused. Ships as a sorry-free direct proof
-- (leaf-bypass), so no sub-goal files are emitted.
theorem s9252 : ∀ (x y z a b : ℝ) (h₀ : 0 < x ∧ 0 < y ∧ 0 < z) (h₁ : x ≠ y) (h₂ : y ≠ z) (h₃ : z ≠ x) (h₄ : x + y + z = a) (h₅ : x ^ 2 + y ^ 2 + z ^ 2 = b ^ 2) (h₆ : x * y = z ^ 2), 0 < a ∧ b ^ 2 < a ^ 2 ∧ a ^ 2 < 3 * b ^ 2  := by
  intro x y z a b h₀ h₁ h₂ h₃ h₄ h₅ h₆
  obtain ⟨hx, hy, hz⟩ := h₀
  have hxy : (x - y) ^ 2 > 0 := by
    have : x - y ≠ 0 := sub_ne_zero.mpr h₁
    positivity
  have hyz : (y - z) ^ 2 > 0 := by
    have : y - z ≠ 0 := sub_ne_zero.mpr h₂
    positivity
  have hzx : (z - x) ^ 2 > 0 := by
    have : z - x ≠ 0 := sub_ne_zero.mpr h₃
    positivity
  refine ⟨?_, ?_, ?_⟩
  · linarith
  · nlinarith [mul_pos hx hy, mul_pos hy hz, mul_pos hz hx, sq_nonneg x, sq_nonneg y, sq_nonneg z]
  · nlinarith [hxy, hyz, hzx, sq_nonneg (x+y+z)]

end Problems.Minif2f.imo_1961_p1
