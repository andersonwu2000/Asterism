import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- source_diff_eq_target: set difference eliminates head?=none, leaving exactly head?=some(1,_)
-- Fin 2 has values 0,1; excluding none and some(0,_) leaves some(1,true/false).
theorem source_diff_eq_target (M : Set E) (wrd : E → FreeGroup (Fin 2)) :
    {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} \
      {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none}
    = {x | x ∈ M ∧
        ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
         (FreeGroup.toWord (wrd x)).head? = some (1, false))} := by
  ext x

  simp only [Set.mem_diff, Set.mem_setOf_eq]
  constructor
  · rintro ⟨⟨hm, hneq0⟩, hnone⟩
    refine ⟨hm, ?_⟩
    rcases h : (FreeGroup.toWord (wrd x)).head? with _ | ⟨⟨i, b⟩⟩
    · exact absurd ⟨hm, h⟩ hnone
    · have hine : i ≠ 0 := by
        intro hi
        apply hneq0
        simp [h, hi]
      have hi1 : i = 1 := by fin_cases i <;> simp_all
      subst hi1
      cases b
      · right; rfl
      · left; rfl
  · rintro ⟨hm, h | h⟩
    · constructor
      · exact ⟨hm, by simp [h]⟩
      · rintro ⟨-, hn⟩; simp [h] at hn
    · constructor
      · exact ⟨hm, by simp [h]⟩
      · rintro ⟨-, hn⟩; simp [h] at hn


end Problems.Geometry.banach_tarski
