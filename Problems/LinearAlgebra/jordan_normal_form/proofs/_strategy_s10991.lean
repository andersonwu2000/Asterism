import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_gap_terms_pos
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_gap_terms_prefix
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_gap_terms_sum

namespace Problems.LinearAlgebra.jordan_normal_form

-- Build gaps `l t = b(t+1) - b t`, extended by `b p := n` (so the last gap is `n - b(last)`):
-- `l := fun t => if (t+1) < p then b⟨t+1⟩ - b t else n - b t`. With the witness fixed, the
-- existential splits into three strictly-simpler facts over the explicit gap term:
--   `gap_terms_pos`    — strict monotonicity / `hlt` make each gap positive;
--   `gap_terms_sum`    — telescoping over all of `Fin p` collapses to `b p - b 0 = n`;
--   `gap_terms_prefix` — telescoping the first `t` gaps recovers `b t`.
-- (Mirror of the proven generic reduction `gaps_from_boundaries`; statement is verbatim equal.)
theorem s10991 {n p : ℕ} (b : Fin p → ℕ)
    (hmono : StrictMono b) (hlt : ∀ t : Fin p, b t < n)
    (hzero : ∀ t : Fin p, (t : ℕ) = 0 → b t = 0)
    (hp : 0 < n → 0 < p) :
    ∃ l : Fin p → ℕ,
      (∀ t : Fin p, 0 < l t) ∧ (∑ t, l t = n) ∧
      (∀ t : Fin p, (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = b t)  := by
  refine ⟨fun t => if h : (t : ℕ) + 1 < p then b ⟨(t : ℕ) + 1, h⟩ - b t else n - b t,
    ?_, ?_, ?_⟩
  · exact gap_terms_pos b hmono hlt hzero hp
  · exact gap_terms_sum b hmono hlt hzero hp
  · exact gap_terms_prefix b hmono hlt hzero hp

end Problems.LinearAlgebra.jordan_normal_form
