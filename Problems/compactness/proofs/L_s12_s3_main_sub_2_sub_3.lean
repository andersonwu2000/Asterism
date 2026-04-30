import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s12_s3_main_sub_2_sub_3 : ∀ {α : Type} (T : Set (PropForm α)) (p : PropForm α),
    ¬Sat (insert p T) →
    ∀ v : Valuation α, (∀ q ∈ T, PropForm.eval v q = true) →
    PropForm.eval v (PropForm.neg p) = true := by
  intro α T p hnotsat v hT
  simp only [PropForm.eval]
  cases h : PropForm.eval v p
  · rfl
  · exfalso
    apply hnotsat
    exact ⟨v, fun q hq => by
      rcases Set.mem_insert_iff.mp hq with rfl | hq
      · exact h
      · exact hT q hq⟩

end Problems.compactness
