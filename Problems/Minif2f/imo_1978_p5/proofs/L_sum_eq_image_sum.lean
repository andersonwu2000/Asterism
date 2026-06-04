import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs

namespace Problems.Minif2f.imo_1978_p5

-- sum_eq_image_sum: Finset.sum_image (injectivity on Icc 1 m) equates the two sums.
theorem sum_eq_image_sum :
    ∀ (n : ℕ) (a : ℕ → ℕ), Function.Injective a → a 0 = 0 →
    ∀ m, m ≤ n →
    (∑ k ∈ Finset.Icc 1 m, (a k : ℝ)) =
      ∑ x ∈ (Finset.Icc 1 m).image a, (x : ℝ) := by
    intro n a ha _ha0 m _hm
    exact (Finset.sum_image (fun x _ y _ h => ha h)).symm

end Problems.Minif2f.imo_1978_p5
