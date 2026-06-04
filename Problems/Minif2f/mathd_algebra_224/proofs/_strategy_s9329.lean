import Mathlib
import Problems.Minif2f.mathd_algebra_224.Defs
import Problems.Minif2f.mathd_algebra_224.proofs.L_mem_implies_sqrt_bound
import Problems.Minif2f.mathd_algebra_224.proofs.L_sqrt_bound_implies_mem

namespace Problems.Minif2f.mathd_algebra_224

-- Split the ∀-iff into its two implications, parameterized over the same n.
-- fwd: sqrt-bound → membership (interval_cases / Real.sqrt monotonicity).
-- bwd: membership → sqrt-bound (fin_cases on the explicit finset, norm_num).
theorem s9329 : ∀ n : ℕ, (Real.sqrt (n : ℝ) < 7/2 ∧ 2 < Real.sqrt (n : ℝ)) ↔
    n ∈ ({5,6,7,8,9,10,11,12} : Finset ℕ) := by
  intro n
  have h_fwd := sqrt_bound_implies_mem n
  have h_bwd := mem_implies_sqrt_bound n
  exact ⟨h_fwd, h_bwd⟩

end Problems.Minif2f.mathd_algebra_224
