import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- A maximal finitely satisfiable set M is neg-decisive and conj-complete:
  (a) p ∉ M ↔ neg p ∈ M  (every formula is decided by M)
  (b) conj p q ∈ M ↔ p ∈ M ∧ q ∈ M  (M is closed under conjunct extraction and introduction) -/
theorem s3_sub_3 {α : Type} (M : Set (PropForm α))
    (hfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hmax : ∀ M' : Set (PropForm α), M ⊆ M' →
        (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M' ⊆ M) :
    (∀ p : PropForm α, p ∉ M ↔ PropForm.neg p ∈ M) ∧
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ p ∈ M ∧ q ∈ M) := by sorry

end Problems.compactness
