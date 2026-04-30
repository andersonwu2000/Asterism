import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- Maximality conversion: Zorn-style maximality (no fin-sat proper superset) implies
the required form (φ ∉ M → insert φ M is not fin-sat). -/
theorem s5_sub_3 {α : Type}
    (M : Set (PropForm α))
    (hMfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMmax : ∀ M' : Set (PropForm α), M ⊆ M' →
      (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M' ⊆ M) :
    ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T := by
  intro φ hφ hfinsat
  have hle : insert φ M ⊆ M := hMmax (insert φ M) (Set.subset_insert φ M) hfinsat
  exact hφ (hle (Set.mem_insert φ M))

end Problems.compactness
