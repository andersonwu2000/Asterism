import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Given the chain inductive step, every finite subset of a nonempty chain's sUnion
-- lies entirely within some single chain element. Proved by Set.Finite.induction_on:
-- base uses nonemptiness; step applies the inductive step hypothesis.
theorem s17_s3_main_sub_1_sub_2 : ∀ {α : Type},
    (∀ (c : Set (Set (PropForm α))), IsChain (· ⊆ ·) c →
        ∀ (T : Set (PropForm α)) (p : PropForm α),
        (∃ X₀ ∈ c, T ⊆ X₀) → (∃ X₁ ∈ c, p ∈ X₁) → ∃ X ∈ c, insert p T ⊆ X) →
    ∀ (c : Set (Set (PropForm α))), IsChain (· ⊆ ·) c → c.Nonempty →
        ∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ c → ∃ X ∈ c, T ⊆ X := by
  sorry

end Problems.compactness
