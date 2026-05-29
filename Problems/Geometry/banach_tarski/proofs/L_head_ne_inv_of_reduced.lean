import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- head_ne_inv_of_reduced: reducedness of x :: M forbids M from starting with x's inverse
-- Uses Red.Step.not cancellation: if M starts with (x.1, !x.2), then x :: M reduces
-- to a strictly shorter list, contradicting hred via a length argument.
theorem head_ne_inv_of_reduced {α : Type*} [DecidableEq α]
    (x : α × Bool) (M : List (α × Bool))
    (hred : FreeGroup.reduce (x :: M) = x :: M) :
    M.head? ≠ some (x.1, !x.2) := by
  intro hcontra
  rw [List.head?_eq_some_iff] at hcontra
  obtain ⟨rest, hrest⟩ := hcontra
  subst hrest
  obtain ⟨c, e⟩ := x
  have hstep : FreeGroup.Red.Step ((c, e) :: (c, !e) :: rest) rest :=
    @FreeGroup.Red.Step.not α [] rest c e
  have heq := FreeGroup.reduce.eq_of_red hstep.to_red
  rw [hred] at heq
  obtain ⟨n, hn⟩ := FreeGroup.Red.length (FreeGroup.reduce.red (L := rest))
  have hlen := congrArg List.length heq
  simp only [List.length_cons] at hlen
  omega

end Problems.Geometry.banach_tarski
