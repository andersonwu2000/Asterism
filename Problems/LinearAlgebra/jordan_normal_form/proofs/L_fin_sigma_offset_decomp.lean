import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- fin_sigma_offset_decomp: q = prefix_sum(block) + within_block offset via finSigmaFinEquiv
-- Rounds through finSigmaFinEquiv_apply: simp closes the roundtrip, linarith extracts arithmetic.
theorem fin_sigma_offset_decomp {p : ℕ} (l : Fin p → ℕ) :
    ∀ q : Fin (∑ t, l t), (q : ℕ) =
      (∑ j : Fin ↑(finSigmaFinEquiv.symm q).1,
        l (Fin.castLE (finSigmaFinEquiv.symm q).1.isLt.le j))
      + ((finSigmaFinEquiv.symm q).2 : ℕ) := by
  intro q
  have h := q.isLt
  have key : (finSigmaFinEquiv (finSigmaFinEquiv.symm q) : ℕ) = (q : ℕ) := by
    simp
  simp only [finSigmaFinEquiv_apply] at key
  linarith [key]

end Problems.LinearAlgebra.jordan_normal_form
