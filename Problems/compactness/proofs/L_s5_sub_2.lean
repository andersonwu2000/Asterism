import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- Zorn application: using the finite cover lemma, every fin-sat set S has a maximal
fin-sat superset M (maximal meaning no fin-sat proper superset exists). -/
theorem s5_sub_2 {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T)
    (hcover : ∀ C : Set (Set (PropForm α)), IsChain (· ⊆ ·) C →
      ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → T.Nonempty → ∃ s ∈ C, T ⊆ s) :
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      (∀ M' : Set (PropForm α), M ⊆ M' →
        (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M' ⊆ M) := by sorry

end Problems.compactness
