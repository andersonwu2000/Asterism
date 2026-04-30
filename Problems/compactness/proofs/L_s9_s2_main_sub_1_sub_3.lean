import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- If M is a maximal finitely-satisfiable superset of S, then any formula outside M
-- witnesses a finite unsatisfiable subset of its insertion.
theorem s9_s2_main_sub_1_sub_3 {α : Type} (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T)
    (M : Set (PropForm α))
    (hSM : S ⊆ M)
    (hMfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMmax : ∀ N : Set (PropForm α),
        S ⊆ N → (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M ⊆ N → N = M) :
    ∀ p : PropForm α, p ∉ M →
        ∃ T : Set (PropForm α), T ⊆ insert p M ∧ T.Finite ∧ ¬Sat T := by sorry

end Problems.compactness
