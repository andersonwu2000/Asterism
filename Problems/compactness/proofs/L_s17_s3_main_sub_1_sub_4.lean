import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Given the chain bound, apply zorn_subset_nonempty to the collection of finsat
-- supersets of S (starting from S itself) to obtain a maximal element M.
-- Maximality: p ∉ M implies insert p M is not finsat, else it would be a strictly
-- larger element of the collection, contradicting maximality.
theorem s17_s3_main_sub_1_sub_4 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ C : Set (Set (PropForm α)), IsChain (· ⊆ ·) C → C.Nonempty →
        (∀ N ∈ C, S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
        S ⊆ ⋃₀ C ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
        S ⊆ M ∧
        (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
        ∀ p : PropForm α, p ∉ M →
            ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) := by
  sorry

end Problems.compactness
