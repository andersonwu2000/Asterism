import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s13_s3_main_sub_1_sub_1 : ∀ {α : Type} (C : Set (Set (PropForm α)))
    (T : Set (PropForm α)),
    IsChain (· ⊆ ·) C → C.Nonempty → T.Finite → T ⊆ ⋃₀ C →
    ∃ M ∈ C, T ⊆ M := by
  sorry

end Problems.compactness
