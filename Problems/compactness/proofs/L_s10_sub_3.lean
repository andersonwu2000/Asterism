import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- If M is a Zorn-maximal fin-sat superset (any fin-sat N with M ⊆ N satisfies N = M),
then adding any φ ∉ M to M destroys fin-sat. -/
theorem s10_sub_3 {α : Type}
    (S : Set (PropForm α))
    (M : Set (PropForm α))
    (hSM     : S ⊆ M)
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax    : ∀ N : Set (PropForm α), M ⊆ N →
                 (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → N = M)
    (φ : PropForm α) (hφ : φ ∉ M) :
    ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T := by
  intro h
  have heq : insert φ M = M := hMax (insert φ M) (Set.subset_insert φ M) h
  have hmem : φ ∈ insert φ M := Set.mem_insert φ M
  rw [heq] at hmem
  exact hφ hmem

end Problems.compactness
