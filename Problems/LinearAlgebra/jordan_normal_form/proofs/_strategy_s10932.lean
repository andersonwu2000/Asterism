import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_gaps_from_boundaries
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_starts_enum_exists

namespace Problems.LinearAlgebra.jordan_normal_form

-- Construct block sizes `l` from start-predicate `S` in two steps.
-- (1) `starts_enum_exists`: enumerate `{q | S q}` in increasing order as a
--     strictly-monotone nat sequence `b` with `b 0 = 0` and `b t < n`.
-- (2) `gaps_from_boundaries`: turn the boundaries `b` into consecutive gaps `l`
--     (positive, summing to `n`, with prefix-sum of first `t` blocks `= b t`).
-- The start-characterisation transfers along `prefix_t = b t`.
theorem s10932 {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q) :
    ∃ (p : ℕ) (l : Fin p → ℕ),
      (∀ t : Fin p, 0 < l t) ∧ (∑ t, l t = n) ∧
      ∀ q : Fin n, (S q ↔ ∃ t : Fin p,
        (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (q : ℕ))  := by
  obtain ⟨p, b, hmono, hlt, hzero, hp, hchar⟩ := starts_enum_exists S h0
  obtain ⟨l, hpos, hsum, hprefix⟩ := gaps_from_boundaries b hmono hlt hzero hp
  refine ⟨p, l, hpos, hsum, fun q => ?_⟩
  rw [hchar q]
  exact exists_congr fun t => by rw [hprefix t]

end Problems.LinearAlgebra.jordan_normal_form
