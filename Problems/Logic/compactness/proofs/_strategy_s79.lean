import Problems.Logic.compactness.Defs
import Problems.Logic.compactness.proofs.L_s79_sub_1
import Problems.Logic.compactness.proofs.L_s79_sub_2
import Problems.Logic.compactness.proofs.L_s79_sub_3

namespace Problems.Logic.compactness

theorem s79 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M := by
  intro α M hfinsat hmax p
  have hwit : ∀ q : PropForm α, q ∉ M →
      ∃ T : Set (PropForm α), T ⊆ M ∧ T.Finite ∧ ¬Sat (insert q T) :=
    s79_sub_2 M hfinsat hmax
  exact ⟨s79_sub_1 M hfinsat p, s79_sub_3 M hfinsat hwit p⟩

end Problems.Logic.compactness
