import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open scoped Pointwise

theorem s186_sub_1 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ,
    (fun x : ℝ => (1 - ξ) / 2 * x) '' cantorXi ξ n = ((1 - ξ) / 2) • cantorXi ξ n := by
  intro ξ hξ hξ1 n
  ext x
  simp only [Set.mem_image, Set.mem_smul_set, Algebra.id.smul_eq_mul]

end Problems.cantor_xi_measure
