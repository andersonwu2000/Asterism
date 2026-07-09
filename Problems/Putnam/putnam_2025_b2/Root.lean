import Mathlib
import Problems.Putnam.putnam_2025_b2.Defs

set_option linter.style.longLine false

open Set Real MeasureTheory Interval

namespace Problems.Putnam.putnam_2025_b2

theorem main : ∀ (f : ℝ → ℝ)
    (hf_cont : ContinuousOn f (Icc 0 1))
    (hf_mono : StrictMonoOn f (Icc 0 1))
    (hf_nonneg : ∀ x ∈ Icc (0 : ℝ) 1, 0 ≤ f x),
(∫ x in (0:ℝ)..1, x * f x) / (∫ x in (0:ℝ)..1, f x) <
    (∫ x in (0:ℝ)..1, x * (f x) ^ 2) / (∫ x in (0:ℝ)..1, (f x) ^ 2) := by sorry

end Problems.Putnam.putnam_2025_b2
