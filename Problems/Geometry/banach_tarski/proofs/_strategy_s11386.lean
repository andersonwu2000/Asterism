import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct proof via `FreeGroup.reduce.cons`: rewrite `reduce (x :: L)` and use `hL` to
-- collapse `reduce L` to `L`, then case on `L`. The nil case is `simp`; the cons case
-- splits on the cancellation condition. The only content needing `hL` (reducedness) is
-- `h_reduced`: a reduced `hd :: tl` cannot have `tl` start with `hd`'s inverse — proved by
-- exhibiting the `Red.Step.not` cancellation and deriving a length contradiction from
-- `reduce.eq_of_red` + `Red.length`. Builds sorry-free; shipped as a leaf.
theorem s11386 {α : Type*} [DecidableEq α]
    (x : α × Bool) (L : List (α × Bool)) (hL : FreeGroup.reduce L = L) :
    (FreeGroup.reduce (x :: L)).head? = some x ↔ L.head? ≠ some (x.1, !x.2)  := by
  rw [FreeGroup.reduce.cons, hL]
  cases L with
  | nil => simp
  | cons hd tl =>
    have h_reduced : tl.head? ≠ some (hd.1, !hd.2) := by
      intro hcontra
      rw [List.head?_eq_some_iff] at hcontra
      obtain ⟨rest, hrest⟩ := hcontra
      subst hrest
      obtain ⟨c, e⟩ := hd
      have hstep : FreeGroup.Red.Step ((c, e) :: (c, !e) :: rest) rest :=
        @FreeGroup.Red.Step.not α [] rest c e
      have heq := FreeGroup.reduce.eq_of_red hstep.to_red
      simp only at hL heq
      rw [hL] at heq
      obtain ⟨n, hn⟩ := FreeGroup.Red.length (FreeGroup.reduce.red (L := rest))
      have hlen := congrArg List.length heq
      simp only [List.length_cons] at hlen
      omega
    obtain ⟨a, b⟩ := x
    obtain ⟨c, d⟩ := hd
    simp only [List.head?_cons]
    split_ifs with hcond
    · obtain ⟨rfl, rfl⟩ := hcond
      simpa [Bool.not_not] using h_reduced
    · simp only [List.head?_cons, Option.some.injEq, Prod.mk.injEq, true_iff, ne_eq, not_and]
      intro hc hd2
      exact hcond ⟨hc.symm, by rw [hd2, Bool.not_not]⟩

end Problems.Geometry.banach_tarski
