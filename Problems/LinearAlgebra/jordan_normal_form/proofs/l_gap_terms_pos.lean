import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- gap_terms_pos: each gap b(t+1)-b(t) (or n-b(last)) is positive via strict monotonicity and hlt
theorem gap_terms_pos {n p : ℕ} (b : Fin p → ℕ)
    (hmono : StrictMono b) (hlt : ∀ t : Fin p, b t < n)
    (hzero : ∀ t : Fin p, (t : ℕ) = 0 → b t = 0)
    (hp : 0 < n → 0 < p) :
    ∀ t : Fin p,
      0 < (if h : (t : ℕ) + 1 < p then b ⟨(t : ℕ) + 1, h⟩ - b t else n - b t) := by
  intro t
  split_ifs with h
  · exact Nat.sub_pos_of_lt (hmono (by simp [Fin.lt_def]))
  · exact Nat.sub_pos_of_lt (hlt t)

end Problems.LinearAlgebra.jordan_normal_form
