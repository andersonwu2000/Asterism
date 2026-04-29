import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- For a chain c, if T ⊆ X₀ ∈ c and p ∈ X₁ ∈ c, the chain property yields
-- insert p T ⊆ some single chain element (take the larger of X₀, X₁).
theorem s17_s3_main_sub_1_sub_1 : ∀ {α : Type} (c : Set (Set (PropForm α))),
    IsChain (· ⊆ ·) c →
    ∀ (T : Set (PropForm α)) (p : PropForm α),
    (∃ X₀ ∈ c, T ⊆ X₀) →
    (∃ X₁ ∈ c, p ∈ X₁) →
    ∃ X ∈ c, insert p T ⊆ X := by
  sorry

end Problems.compactness
