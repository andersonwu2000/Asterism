import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s6_s3_main_sub_1_sub_4 : ∀ {α : Type} (S M : Set (PropForm α)),
    S ⊆ M →
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ N : Set (PropForm α), S ⊆ N →
      (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M ⊆ N → N = M) →
    ∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) := by
  intro α S M hSM _ hMax p hpM hContra
  have hSN : S ⊆ insert p M := hSM.trans (Set.subset_insert p M)
  have heq : insert p M = M := hMax (insert p M) hSN hContra (Set.subset_insert p M)
  have hp : p ∈ insert p M := Set.mem_insert_iff.mpr (Or.inl rfl)
  rw [heq] at hp
  exact hpM hp

end Problems.compactness
