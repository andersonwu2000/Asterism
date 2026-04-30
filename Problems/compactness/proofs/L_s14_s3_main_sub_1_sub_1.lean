import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s14_s3_main_sub_1_sub_1 : ∀ {α : Type} (c : Set (Set α)),
    IsChain (· ⊆ ·) c → c.Nonempty →
    ∀ T : Set α, T.Finite → T ⊆ ⋃₀ c → ∃ M ∈ c, T ⊆ M := by
  sorry

end Problems.compactness
