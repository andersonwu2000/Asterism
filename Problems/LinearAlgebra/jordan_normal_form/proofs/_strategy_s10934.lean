import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_gaps_pos
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_gaps_prefix
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_gaps_sum

namespace Problems.LinearAlgebra.jordan_normal_form

-- Build gaps `l` from boundaries `b` with `l t = b(t+1) - b t` (extended by `b p = n`),
-- i.e. `l t = if (t+1) < p then b⟨t+1⟩ - b t else n - b t`.  Three independent facts:
-- `gaps_pos` (strict mono ⇒ each gap positive), `gaps_sum` (telescoping over all of `Fin p`
-- gives `n`), `gaps_prefix` (telescoping of the first `t` gaps gives `b t`).  Each fixes the
-- witness, so is strictly simpler than the existential; sum/prefix reduce to
-- `Finset.sum_range_tsub` after `Fin.sum_univ_eq_sum_range`.
theorem s10934 {n p : ℕ} (b : Fin p → ℕ)
    (hmono : StrictMono b) (hlt : ∀ t : Fin p, b t < n)
    (hzero : ∀ t : Fin p, (t : ℕ) = 0 → b t = 0)
    (hp : 0 < n → 0 < p) :
    ∃ l : Fin p → ℕ,
      (∀ t : Fin p, 0 < l t) ∧ (∑ t, l t = n) ∧
      (∀ t : Fin p, (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = b t)  := by
  refine ⟨fun t => if h : (t : ℕ) + 1 < p then b ⟨(t : ℕ) + 1, h⟩ - b t else n - b t,
    ?_, ?_, ?_⟩
  · exact gaps_pos b hmono hlt hzero hp
  · exact gaps_sum b hmono hlt hzero hp
  · exact gaps_prefix b hmono hlt hzero hp

end Problems.LinearAlgebra.jordan_normal_form
