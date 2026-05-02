import Problems.compactness.Defs
import Problems.compactness.proofs.L_s79_sub_1
import Problems.compactness.proofs.L_s79_sub_2
import Problems.compactness.proofs.L_s79_sub_3

namespace Problems.compactness

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

end Problems.compactness
