import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct proof (leaf): tail of a reduced word is reduced.
-- Rewrite `reduce (x :: M)` via `reduce.cons` and case on `reduce M`.
--   • `reduce M = []`  : then `[x] = x :: M`, so `M = []` and `reduce M = M`.
--   • `reduce M = hd :: tl` : `reduce.cons` gives an `if`. The cancelling branch
--     forces `reduce M = hd :: x :: M`, contradicting `(reduce M).length ≤ M.length`
--     (`reduce.red` + `Red.length`); the non-cancelling branch gives `x :: hd :: tl = x :: M`,
--     whence `hd :: tl = M`, i.e. `reduce M = M`.
theorem s11401 {α : Type*} [DecidableEq α]
    (x : α × Bool) (M : List (α × Bool))
    (h : FreeGroup.reduce (x :: M) = x :: M) :
    FreeGroup.reduce M = M  := by
  rw [FreeGroup.reduce.cons] at h
  rcases hM : FreeGroup.reduce M with _ | ⟨hd, tl⟩
  · rw [hM] at h
    exact (List.cons.inj h).2
  · rw [hM] at h
    simp only at h
    split_ifs at h with hc
    · exfalso
      obtain ⟨n, hn⟩ := FreeGroup.Red.length (FreeGroup.reduce.red (L := M))
      rw [hM, h] at hn
      simp at hn
      omega
    · exact (List.cons.inj h).2

end Problems.Geometry.banach_tarski
