import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- If every set in a ⊆-chain C is finitely satisfiable, then ⋃₀ C is finitely satisfiable.
Key: any finite T ⊆ ⋃₀ C is covered by a single maximal chain member. -/
theorem s3_sub_1 {α : Type}
    (C : Set (Set (PropForm α)))
    (hchain : IsChain (· ⊆ ·) C)
    (hfinsat : ∀ s ∈ C, ∀ T : Set (PropForm α), T ⊆ s → T.Finite → Sat T)
    (T : Set (PropForm α)) (hT : T ⊆ ⋃₀ C) (hfin : T.Finite) :
    Sat T := by sorry

end Problems.compactness
