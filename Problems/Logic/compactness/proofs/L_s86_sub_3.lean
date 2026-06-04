import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s86_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∃ M : Set (PropForm α),
      (S ⊆ M ∧ (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)) ∧
      (∀ N : Set (PropForm α),
        (S ⊆ N ∧ (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T)) →
        M ⊆ N → M = N)) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α), M ⊆ N →
        (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N := by
  intro α S ⟨M, ⟨hSM, hMfinsat⟩, hMmax⟩
  exact ⟨M, hSM, hMfinsat, fun N hMN hNfinsat => hMmax N ⟨hSM.trans hMN, hNfinsat⟩ hMN⟩

end Problems.Logic.compactness
