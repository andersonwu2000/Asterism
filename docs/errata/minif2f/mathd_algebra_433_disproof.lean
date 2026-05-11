/-
  Sandbox disproof of the minif2f-transcribed statement of
  `mathd_algebra_433`.

  ## Background
  Statement (as imported):
    ∀ (f : ℝ → ℝ) (h₀ : ∀ x, f x = 3 * Real.sqrt (2 * x - 7) - 8),
      f 8 = 19

  ## Bug
  Simple arithmetic error in the expected answer. f(8) = 3·√(2·8 - 7) - 8
    = 3·√9 - 8 = 3·3 - 8 = 1, not 19. The MATH-dataset source problem
  presumably had a different value or asked for f at a different point.

  Counterexample: f x = 3·√(2x - 7) - 8 itself satisfies h₀ reflexively
  but f(8) = 1.

  ## How to verify
    cd D:/Asterism
    lake env lean docs/errata/minif2f/mathd_algebra_433_disproof.lean
  Expected: clean elaboration; axioms = [propext, Classical.choice, Quot.sound].
-/
import Mathlib

namespace Minif2fErrata.MathdAlgebra433

def stmt : Prop :=
  ∀ (f : ℝ → ℝ) (_ : ∀ x, f x = 3 * Real.sqrt (2 * x - 7) - 8),
    f 8 = 19

theorem disproof : ¬ stmt := by
  intro h
  -- Use the formula itself as f.
  let f : ℝ → ℝ := fun x => 3 * Real.sqrt (2 * x - 7) - 8
  have h0 : ∀ x : ℝ, f x = 3 * Real.sqrt (2 * x - 7) - 8 := fun _ => rfl
  have key := h f h0
  -- key : f 8 = 19, i.e. 3 * √9 - 8 = 19
  have hf8 : f 8 = 1 := by
    show 3 * Real.sqrt (2 * 8 - 7) - 8 = 1
    have h9 : (2 * (8 : ℝ) - 7) = 9 := by norm_num
    rw [h9]
    have : Real.sqrt 9 = 3 := by
      rw [show (9 : ℝ) = 3 ^ 2 from by norm_num,
          Real.sqrt_sq (by norm_num : (0 : ℝ) ≤ 3)]
    rw [this]
    norm_num
  rw [hf8] at key
  norm_num at key

end Minif2fErrata.MathdAlgebra433

#print axioms Minif2fErrata.MathdAlgebra433.disproof
