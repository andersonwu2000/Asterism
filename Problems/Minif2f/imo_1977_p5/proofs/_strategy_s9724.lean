import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs
import Problems.Minif2f.imo_1977_p5.proofs.L_x_sq_in_225_784

namespace Problems.Minif2f.imo_1977_p5

-- Decomposition: the heavy lifting (which values x^2 can take when
-- x^2+y^2=1009 with |x|,|y|≤31) is pushed into `x_sq_in_225_784`.
-- Given that, the s9724 conclusion follows by simple linarith:
-- y^2 = 1009 - x^2 = 784 or 225 respectively.
theorem s9724 : ∀ (x y : ℤ), -31 ≤ x → x ≤ 31 → -31 ≤ y → y ≤ 31 →
    x ^ 2 + y ^ 2 = 1009 → (x ^ 2 = 225 ∧ y ^ 2 = 784) ∨ (x ^ 2 = 784 ∧ y ^ 2 = 225)  := by
  intro x y hx1 hx2 hy1 hy2 hxy
  have hxs : x ^ 2 = 225 ∨ x ^ 2 = 784 :=
    x_sq_in_225_784 x y hx1 hx2 hy1 hy2 hxy
  rcases hxs with h | h
  · left
    refine ⟨h, ?_⟩
    linarith
  · right
    refine ⟨h, ?_⟩
    linarith

end Problems.Minif2f.imo_1977_p5
