import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s10915

namespace Problems.LinearAlgebra.jordan_normal_form


-- entry_kind: Builder
-- block_enum: existence of a Fin-indexed enumeration of Σ s : Fin r, Fin (k s)
-- with consecutive-index iff within-block adjacency; delegates to block_enum_consecutive (s10915).
theorem block_enum (r : ℕ) (k : Fin r → ℕ) :
    ∃ e : Fin (∑ s, k s) ≃ Σ s : Fin r, Fin (k s),
      ∀ p q : Fin (∑ s, k s),
        (e p).1 = (e q).1 →
          (((e p).2 : ℕ) + 1 = ((e q).2 : ℕ) ↔ (p : ℕ) + 1 = (q : ℕ)) := by
  exact s10915 k

end Problems.LinearAlgebra.jordan_normal_form

