import Mathlib
import Problems.Logic.compactness.Defs
import Problems.Logic.compactness.proofs.L_s87_sub_1
import Problems.Logic.compactness.proofs.L_s87_sub_2

namespace Problems.Logic.compactness

theorem s87 : ∀ {α : Type} (C : Set (Set (PropForm α))),
    C.Nonempty →
    IsChain (· ⊆ ·) C →
    (∀ X ∈ C, ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
    ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T := by
  intro α C hCne hChain hfinsat T hTC hTfin
  exact s87_sub_2 C hfinsat T hTfin (s87_sub_1 C hCne hChain T hTC hTfin)

end Problems.Logic.compactness
