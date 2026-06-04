import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s78_sub_4 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ N : Set (PropForm α), M ⊆ N →
      (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N) →
    ∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) := by
  intro α M _hfinsat hmax p hp hinsert
  have hsubset : M ⊆ insert p M := Set.subset_insert p M
  have heq : M = insert p M := hmax (insert p M) hsubset hinsert
  have hmem : p ∈ insert p M := Set.mem_insert p M
  rw [← heq] at hmem
  exact hp hmem

end Problems.Logic.compactness
