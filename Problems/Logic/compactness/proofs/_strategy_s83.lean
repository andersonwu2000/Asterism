import Problems.Logic.compactness.Defs
import Problems.Logic.compactness.proofs.L_s83_sub_1
import Problems.Logic.compactness.proofs.L_s83_sub_2
import Problems.Logic.compactness.proofs.L_s83_sub_3

namespace Problems.Logic.compactness

theorem s83 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, p ∉ M →
      ∃ T : Set (PropForm α), T ⊆ M ∧ T.Finite ∧ ¬Sat (insert p T) := by
  intro α M hfinsat hmax p hp
  have h1 : ∃ T' : Set (PropForm α), T' ⊆ insert p M ∧ T'.Finite ∧ ¬Sat T' :=
    s83_sub_1 M hfinsat hmax p hp
  obtain ⟨T', hT'sub, hT'fin, hT'unsat⟩ := h1
  have h2 : p ∈ T' := s83_sub_2 M hfinsat hmax p hp T' hT'sub hT'fin hT'unsat
  exact s83_sub_3 M hfinsat hmax p hp T' hT'sub hT'fin hT'unsat h2

end Problems.Logic.compactness
