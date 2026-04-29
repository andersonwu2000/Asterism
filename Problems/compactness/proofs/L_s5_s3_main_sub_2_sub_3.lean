import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s5_s3_main_sub_2_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α,
    ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) →
    ∃ T₁ : Set (PropForm α), T₁ ⊆ M ∧ T₁.Finite ∧ ¬Sat (insert p T₁) := by
  intro α M hfinsat _hmax p hnot
  push_neg at hnot
  obtain ⟨T, hTsub, hTfin, hTunsat⟩ := hnot
  by_cases hp : p ∈ T
  · refine ⟨T \ {p}, ?_, hTfin.subset Set.diff_subset, ?_⟩
    · intro x hx
      simp only [Set.mem_diff, Set.mem_singleton_iff] at hx
      have hmem := hTsub hx.1
      rw [Set.mem_insert_iff] at hmem
      exact hmem.resolve_left hx.2
    · rw [Set.insert_diff_singleton, Set.insert_eq_of_mem hp]
      exact hTunsat
  · exact absurd (hfinsat T (fun x hx => by
        have hmem := hTsub hx
        rw [Set.mem_insert_iff] at hmem
        exact hmem.resolve_left (fun h => hp (h ▸ hx))) hTfin) hTunsat

end Problems.compactness
