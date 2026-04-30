import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- The union of a nonempty chain of finitely-satisfiable supersets of S is again
-- a finitely-satisfiable superset of S.
theorem s9_s2_main_sub_1_sub_2 {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T)
    (C : Set (Set (PropForm α)))
    (hC_chain : IsChain (· ⊆ ·) C)
    (hCne : C.Nonempty)
    (hC_mem : ∀ N ∈ C, S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) :
    S ⊆ ⋃₀ C ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T := by sorry

end Problems.compactness
