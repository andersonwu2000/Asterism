import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s83_sub_2 {α : Type} (M : Set (PropForm α))
    (hfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (_hmax : ∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T))
    (p : PropForm α) (_hp : p ∉ M)
    (T' : Set (PropForm α)) (hT'sub : T' ⊆ insert p M)
    (hT'fin : T'.Finite) (hT'unsat : ¬Sat T') : p ∈ T' := by
  by_contra h_not_mem
  apply hT'unsat
  apply hfinsat T' _ hT'fin
  intro x hx
  rcases hT'sub hx with rfl | hm
  · exact absurd hx h_not_mem
  · exact hm

end Problems.Logic.compactness
