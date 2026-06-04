import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs
import Problems.Minif2f.imo_1977_p5.proofs.L_abs_eq_15_of_sq_225
import Problems.Minif2f.imo_1977_p5.proofs.L_abs_eq_28_of_sq_784
import Problems.Minif2f.imo_1977_p5.proofs.L_sq_dichotomy_1009

namespace Problems.Minif2f.imo_1977_p5

-- Reduce ℤ-box dispatch to a square-value dichotomy + two abs-from-square lemmas.
-- sq_dichotomy_1009 carries the bounds and the equation and dispatches on which
-- variable holds the 225-square vs the 784-square (the heavy interval-cases part);
-- abs_eq_15_of_sq_225 and abs_eq_28_of_sq_784 are abstract algebraic facts that
-- recover |z| from z^2 without bounds.
theorem s9686 : ∀ (x y : ℤ), -31 ≤ x → x ≤ 31 → -31 ≤ y → y ≤ 31 →
    x ^ 2 + y ^ 2 = 1009 → (abs x = 15 ∧ abs y = 28) ∨ (abs x = 28 ∧ abs y = 15)  := by
  intro x y hx1 hx2 hy1 hy2 hxy
  have h_dich := sq_dichotomy_1009 x y hx1 hx2 hy1 hy2 hxy
  rcases h_dich with ⟨hx2', hy2'⟩ | ⟨hx2', hy2'⟩
  · exact Or.inl ⟨abs_eq_15_of_sq_225 x hx2', abs_eq_28_of_sq_784 y hy2'⟩
  · exact Or.inr ⟨abs_eq_28_of_sq_784 x hx2', abs_eq_15_of_sq_225 y hy2'⟩

end Problems.Minif2f.imo_1977_p5
