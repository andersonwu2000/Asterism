import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
theorem gap_terms_sum {n p : ℕ} (b : Fin p → ℕ)
    (hmono : StrictMono b) (hlt : ∀ t : Fin p, b t < n)
    (hzero : ∀ t : Fin p, (t : ℕ) = 0 → b t = 0)
    (hp : 0 < n → 0 < p) :
    (∑ t : Fin p,
      (if h : (t : ℕ) + 1 < p then b ⟨(t : ℕ) + 1, h⟩ - b t else n - b t)) = n := by sorry

end Problems.LinearAlgebra.jordan_normal_form
