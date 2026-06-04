import Mathlib
import Problems.Minif2f.aime_1991_p1.Defs

namespace Problems.Minif2f.aime_1991_p1

-- Leaf: brute-force search after bounding x, y ≤ 35.
-- From h₀ (x, y ≥ 1) and h₁ (xy + x + y = 71), `nlinarith` derives x ≤ 35 and y ≤ 35.
-- `interval_cases` enumerates the 35*35 = 1225 pairs; `omega` discharges each
-- via the linear/numerical hypotheses (h₁ linear, h₂ numerical once x,y are constants).
theorem s9358 :
    ∀ (x y : ℕ) (h₀ : 0 < x ∧ 0 < y) (h₁ : x * y + (x + y) = 71)
      (h₂ : x ^ 2 * y + x * y ^ 2 = 880),
      x + y = 16  := by
  intro x y h₀ h₁ h₂
  obtain ⟨hx, hy⟩ := h₀
  have hxle : x ≤ 35 := by nlinarith
  have hyle : y ≤ 35 := by nlinarith
  interval_cases x <;> interval_cases y <;> omega

end Problems.Minif2f.aime_1991_p1
