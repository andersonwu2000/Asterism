import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Inner lemma: if T₀ ⊆ M is finite and insert φ T₀ is unsat, then insert (neg φ) T' is sat
-- for any finite T' ⊆ M. (Any model of T₀ ∪ T' must falsify φ, hence satisfy neg φ.)
theorem s9_sub_3 {α : Type} (M : Set (PropForm α))
    (hFinSat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hMax : ∀ φ : PropForm α, φ ∉ M →
      ¬ ∀ T : Set (PropForm α), T ⊆ insert φ M → T.Finite → Sat T)
    (φ : PropForm α)
    (T₀ : Set (PropForm α)) (hT₀M : T₀ ⊆ M) (hT₀fin : T₀.Finite)
    (hT₀bad : ¬ Sat (insert φ T₀))
    (T' : Set (PropForm α)) (hT'M : T' ⊆ M) (hT'fin : T'.Finite)
    : Sat (insert (PropForm.neg φ) T') := by
  obtain ⟨v, hv⟩ := hFinSat (T₀ ∪ T') (Set.union_subset hT₀M hT'M) (hT₀fin.union hT'fin)
  have hφ : PropForm.eval v φ = false := by
    apply Bool.eq_false_of_not_eq_true
    intro htrue
    exact hT₀bad ⟨v, fun p hp => by
      simp only [Set.mem_insert_iff] at hp
      rcases hp with rfl | hmem
      · exact htrue
      · exact hv p (Set.mem_union_left T' hmem)⟩
  exact ⟨v, fun p hp => by
    simp only [Set.mem_insert_iff] at hp
    rcases hp with rfl | hmem
    · simp [PropForm.eval, hφ]
    · exact hv p (Set.mem_union_right T₀ hmem)⟩

end Problems.compactness
