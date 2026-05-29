import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct leaf: the 5-piece base disjointness is pairwise-distinct head-key separation.
-- After `Set.disjoint_left`, case-split both indices: a word in the empty-word piece
-- (`toWord = []`) has `head? = none`, contradicting any `head? = some p`; two `some`
-- pieces with distinct keys contradict equal `head?`. `simp_all` + `toWord_one` closes all.
theorem s11416 :
    (Set.univ : Set (Option (Fin 2 × Bool))).PairwiseDisjoint
      (fun o => match o with
        | none   => {w : FreeGroup (Fin 2) | FreeGroup.toWord w = []}
        | some p => {w : FreeGroup (Fin 2) | (FreeGroup.toWord w).head? = some p})  := by
  intro o₁ _ o₂ _ hne
  simp only [Function.onFun]
  rw [Set.disjoint_left]
  intro w hw1 hw2
  cases o₁ <;> cases o₂ <;>
    simp_all [FreeGroup.toWord_one]

end Problems.Geometry.banach_tarski
