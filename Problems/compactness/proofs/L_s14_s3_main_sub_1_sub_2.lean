import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s14_s3_main_sub_1_sub_2 : ∀ {α : Type} (S : Set (PropForm α))
    (c : Set (Set (PropForm α))),
    c.Nonempty →
    IsChain (· ⊆ ·) c →
    (∀ M ∈ c, S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ c → ∃ M ∈ c, T ⊆ M) →
    S ⊆ ⋃₀ c ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ c → T.Finite → Sat T := by
  sorry

end Problems.compactness
