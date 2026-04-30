import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- Chain cover: any finite subset of the union of a ⊆-chain is contained in
some single member of the chain. -/
theorem s8_sub_1 {α : Type}
    (C : Set (Set (PropForm α)))
    (hchain : IsChain (· ⊆ ·) C)
    (T : Set (PropForm α)) (hT : T ⊆ ⋃₀ C) (hfin : T.Finite) :
    ∃ N ∈ C, T ⊆ N := by sorry

end Problems.compactness
