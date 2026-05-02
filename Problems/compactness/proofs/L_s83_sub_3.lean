import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s83_sub_3 {α : Type} (M : Set (PropForm α))
    (_hfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (_hmax : ∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T))
    (p : PropForm α) (_hp : p ∉ M)
    (T' : Set (PropForm α)) (hT'sub : T' ⊆ insert p M) (hT'fin : T'.Finite)
    (hT'unsat : ¬Sat T') (hpT' : p ∈ T') :
    ∃ T₀ : Set (PropForm α), T₀ ⊆ M ∧ T₀.Finite ∧ ¬Sat (insert p T₀) := by
  refine ⟨T' \ {p}, ?_, ?_, ?_⟩
  · intro x hx
    simp only [Set.mem_diff, Set.mem_singleton_iff] at hx
    obtain ⟨hxT', hxnp⟩ := hx
    rcases Set.mem_insert_iff.mp (hT'sub hxT') with rfl | hxM
    · exact absurd rfl hxnp
    · exact hxM
  · exact hT'fin.subset Set.diff_subset
  · have heq : insert p (T' \ {p}) = T' := by
      ext x
      simp only [Set.mem_insert_iff, Set.mem_diff, Set.mem_singleton_iff]
      constructor
      · rintro (rfl | ⟨hx, -⟩)
        · exact hpT'
        · exact hx
      · intro hx
        by_cases h : x = p
        · exact Or.inl h
        · exact Or.inr ⟨hx, h⟩
    rw [heq]
    exact hT'unsat

end Problems.compactness
