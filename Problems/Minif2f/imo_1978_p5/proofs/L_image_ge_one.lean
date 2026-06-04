import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs

namespace Problems.Minif2f.imo_1978_p5

-- entry_kind: Builder
theorem image_ge_one :
    ∀ (n : ℕ) (a : ℕ → ℕ), Function.Injective a → a 0 = 0 →
    ∀ m, m ≤ n →
    ∀ x ∈ (Finset.Icc 1 m).image a, 1 ≤ x := by grind

end Problems.Minif2f.imo_1978_p5
