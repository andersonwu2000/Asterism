import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s15_s3_main_sub_1_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∀ (c : Set (Set (PropForm α))), IsChain (· ⊆ ·) c → c.Nonempty →
    ∀ (T : Set (PropForm α)), T.Finite → T ⊆ ⋃₀ c → ∃ M ∈ c, T ⊆ M := by
  sorry

end Problems.compactness
