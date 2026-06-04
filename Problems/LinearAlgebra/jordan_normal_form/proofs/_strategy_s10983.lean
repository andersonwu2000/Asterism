import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_gaps_for_starts
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_start_iff_g_val

namespace Problems.LinearAlgebra.jordan_normal_form

-- Read the gap lengths off the given monotone start-enumeration `g`: set boundaries
-- `b t := (g t : ℕ)`, build the gaps from those boundaries, and transfer the start
-- characterisation along the prefix-sum identity `prefix_t = (g t : ℕ)`.
--   `gaps_for_starts` — gaps `l` (positive, summing to `n`) whose `t`-th prefix sum is `(g t : ℕ)`.
--   `start_iff_g_val` — `S q` iff `q` is one of the enumerated start values `(g t : ℕ)`.
-- Both are strictly simpler: the first drops the `S`-characterisation to a per-index identity,
-- the second is a pure `hrange` + `Fin.val`-injectivity rewrite.
theorem s10983 {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    ∃ (l : Fin p → ℕ),
      (∀ t : Fin p, 0 < l t) ∧ (∑ t, l t = n) ∧
      (∀ q : Fin n, (S q ↔ ∃ t : Fin p,
        (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (q : ℕ)))  := by
  have h_gaps := gaps_for_starts S h0 p g hmono hrange
  have h_iff := start_iff_g_val S h0 p g hmono hrange
  obtain ⟨l, hpos, hsum, hprefix⟩ := h_gaps
  refine ⟨l, hpos, hsum, fun q => ?_⟩
  rw [h_iff q]
  exact exists_congr fun t => by rw [hprefix t]

end Problems.LinearAlgebra.jordan_normal_form
