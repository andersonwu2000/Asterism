import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_offset_block_enum

namespace Problems.LinearAlgebra.jordan_normal_form

-- Reduce the within-block consecutive-index iff to a coordinate formula.
-- Sub-goal `offset_block_enum` supplies an enumeration `e` plus per-block
-- offsets `o` with `(p : ℕ) = o (e p).1 + (e p).2`; on a shared block the
-- offsets cancel, so the consecutive-index equivalence is pure `omega`.
theorem s10915 {ι : Type*} [Fintype ι] (k : ι → ℕ) :
    ∃ e : Fin (∑ s, k s) ≃ Σ s : ι, Fin (k s),
      ∀ p q : Fin (∑ s, k s),
        (e p).1 = (e q).1 →
          (((e p).2 : ℕ) + 1 = ((e q).2 : ℕ) ↔ (p : ℕ) + 1 = (q : ℕ))  := by
  have h_enum := offset_block_enum k
  obtain ⟨e, o, he⟩ := h_enum
  refine ⟨e, fun p q hpq => ?_⟩
  have hp := he p
  have hq := he q
  have ho : o (e p).fst = o (e q).fst := by rw [hpq]
  omega

end Problems.LinearAlgebra.jordan_normal_form
