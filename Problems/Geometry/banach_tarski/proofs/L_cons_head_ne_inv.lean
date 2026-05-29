import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- cons_head_ne_inv: a reduced list `x :: M` cannot have `M` start with `x`'s inverse;
-- proved by Red.Step.not cancellation + length contradiction via reduce.eq_of_red.
theorem cons_head_ne_inv (x : Fin 2 × Bool) (M : List (Fin 2 × Bool))
    (hred : FreeGroup.reduce (x :: M) = x :: M) (hne : M ≠ []) :
    M.head? ≠ some (x.1, !x.2) := by
  intro hcontra
  rw [List.head?_eq_some_iff] at hcontra
  obtain ⟨rest, hrest⟩ := hcontra
  subst hrest
  obtain ⟨c, e⟩ := x
  simp only at hred
  have hstep : FreeGroup.Red.Step ((c, e) :: (c, !e) :: rest) rest :=
    @FreeGroup.Red.Step.not (Fin 2) [] rest c e
  have heq := FreeGroup.reduce.eq_of_red hstep.to_red
  simp only at heq
  rw [hred] at heq
  obtain ⟨n, hn⟩ := FreeGroup.Red.length (FreeGroup.reduce.red (L := rest))
  have hlen := congrArg List.length heq
  simp only [List.length_cons] at hlen hn
  omega

end Problems.Geometry.banach_tarski
