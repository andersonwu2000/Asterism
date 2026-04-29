import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s8_s3_main_sub_2_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∉ M →
      ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T)) →
    ∀ p : PropForm α, p ∉ M →
      ∃ F : Set (PropForm α), F ⊆ M ∧ F.Finite ∧ ¬Sat (insert p F) := by
  intro α M hfinsat hMmax p hp
  push_neg at hMmax
  obtain ⟨T, hT_sub, hT_fin, hT_unsat⟩ := hMmax p hp
  refine ⟨T \ {p}, ?_, hT_fin.diff, ?_⟩
  · intro x hx
    simp only [Set.mem_diff, Set.mem_singleton_iff] at hx
    have hx_in := hT_sub hx.1
    rw [Set.mem_insert_iff] at hx_in
    exact hx_in.resolve_left hx.2
  · by_cases hpT : p ∈ T
    · rw [Set.insert_diff_singleton, Set.insert_eq_of_mem hpT]
      exact hT_unsat
    · exact absurd (hfinsat T (fun x hxT => by
          have hx_in := hT_sub hxT
          rw [Set.mem_insert_iff] at hx_in
          exact hx_in.resolve_left fun h => hpT (h ▸ hxT)) hT_fin) hT_unsat

end Problems.compactness
