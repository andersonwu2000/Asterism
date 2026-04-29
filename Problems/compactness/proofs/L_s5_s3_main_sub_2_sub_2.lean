import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s5_s3_main_sub_2_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ (p : PropForm α) (T : Set (PropForm α)),
    Sat T → ¬Sat (insert p T) → Sat (insert (PropForm.neg p) T) := by
  intro α M _hfinsat _hmax p T ⟨v, hv⟩ hnosat
  refine ⟨v, fun q hq => ?_⟩
  rcases Set.mem_insert_iff.mp hq with rfl | hqT
  · have heval_false : PropForm.eval v p = false := by
      cases hb : PropForm.eval v p with
      | false => rfl
      | true =>
        exfalso
        apply hnosat
        exact ⟨v, fun r hr => by
          rcases Set.mem_insert_iff.mp hr with rfl | hrT
          · exact hb
          · exact hv r hrT⟩
    simp [PropForm.eval, heval_false]
  · exact hv q hqT

end Problems.compactness
