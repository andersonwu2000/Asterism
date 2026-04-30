import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- For a chain C and a nonempty finite T ⊆ ⋃₀ C, some chain member covers T.
theorem s9_s2_main_sub_1_sub_1 {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T)
    (C : Set (Set (PropForm α)))
    (hC_chain : IsChain (· ⊆ ·) C)
    (T : Set (PropForm α))
    (hTne : T.Nonempty)
    (hT_sub : T ⊆ ⋃₀ C)
    (hT_fin : T.Finite) :
    ∃ N ∈ C, T ⊆ N := by sorry

end Problems.compactness
