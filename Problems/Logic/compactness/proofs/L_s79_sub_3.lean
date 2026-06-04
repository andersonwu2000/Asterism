import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s79_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ∃ T : Set (PropForm α), T ⊆ M ∧ T.Finite ∧ ¬Sat (insert p T)) →
    ∀ p : PropForm α, p ∉ M → PropForm.neg p ∈ M := by
  intro α M hfinsat hwit p hp
  by_contra hn
  obtain ⟨T₁, hT₁sub, hT₁fin, hT₁unsat⟩ := hwit p hp
  obtain ⟨T₂, hT₂sub, hT₂fin, hT₂unsat⟩ := hwit (PropForm.neg p) hn
  obtain ⟨v, hv⟩ := hfinsat (T₁ ∪ T₂) (Set.union_subset hT₁sub hT₂sub) (hT₁fin.union hT₂fin)
  have hv₁ : ∀ q ∈ T₁, PropForm.eval v q = true := fun q hq => hv q (Or.inl hq)
  have hv₂ : ∀ q ∈ T₂, PropForm.eval v q = true := fun q hq => hv q (Or.inr hq)
  have hevp : PropForm.eval v p = false := by
    cases hb : PropForm.eval v p with
    | false => rfl
    | true =>
      exfalso
      exact hT₁unsat ⟨v, fun q hq => by
        rcases Set.mem_insert_iff.mp hq with rfl | hq'
        · exact hb
        · exact hv₁ q hq'⟩
  exact hT₂unsat ⟨v, fun q hq => by
    rcases Set.mem_insert_iff.mp hq with rfl | hq'
    · simp [PropForm.eval, hevp]
    · exact hv₂ q hq'⟩

end Problems.Logic.compactness
