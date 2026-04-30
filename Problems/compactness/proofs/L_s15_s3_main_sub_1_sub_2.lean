import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s15_s3_main_sub_1_sub_2 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∀ (c : Set (Set (PropForm α))),
      (∀ M ∈ c, S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
      IsChain (· ⊆ ·) c → c.Nonempty →
      (∀ (T : Set (PropForm α)), T.Finite → T ⊆ ⋃₀ c → ∃ M ∈ c, T ⊆ M) →
      S ⊆ ⋃₀ c ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ c → T.Finite → Sat T := by
  sorry

end Problems.compactness
