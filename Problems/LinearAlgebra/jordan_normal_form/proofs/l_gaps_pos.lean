import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- gaps_pos: each gap l t = b(t+1) - b t (or n - b(last)) is strictly positive
-- In the successor case, StrictMono b gives b t < b(t+1); in the last case, hlt t gives b t < n.
theorem gaps_pos {n p : ℕ} (b : Fin p → ℕ)
    (hmono : StrictMono b) (hlt : ∀ t : Fin p, b t < n)
    (hzero : ∀ t : Fin p, (t : ℕ) = 0 → b t = 0)
    (hp : 0 < n → 0 < p) :
    ∀ t : Fin p,
      0 < (if h : (t : ℕ) + 1 < p then b ⟨(t : ℕ) + 1, h⟩ - b t else n - b t) := by
  intro t
  split_ifs with h
  · apply Nat.sub_pos_of_lt
    apply hmono
    simp [Fin.lt_def]

  · apply Nat.sub_pos_of_lt
    exact hlt t

end Problems.LinearAlgebra.jordan_normal_form
