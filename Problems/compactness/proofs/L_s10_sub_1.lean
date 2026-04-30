import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- If every set in a ⊆-chain C is finitely satisfiable, then ⋃₀ C is
finitely satisfiable. Key: any finite T ⊆ ⋃₀ C is covered by a single
chain member (or T = ∅ when C = ∅). -/
theorem s10_sub_1 {α : Type}
    (C : Set (Set (PropForm α)))
    (hChain : IsChain (· ⊆ ·) C)
    (hFinSat : ∀ N ∈ C, ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T)
    (T : Set (PropForm α)) (hT : T ⊆ ⋃₀ C) (hFin : T.Finite) :
    Sat T := by
  sorry

end Problems.compactness
