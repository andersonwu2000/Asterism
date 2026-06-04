import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_succ_kills_f_pow_v_base
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_succ_kills_f_pow_v_step

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Decompose by induction on `k`:
--   * `e_pow_succ_kills_f_pow_v_base`: k=0 — `e v = 0` from the primitive vector
--     hypothesis, so `e^1 (f^0 v) = 0` is immediate.
--   * `e_pow_succ_kills_f_pow_v_step`: given IH at k, push `e` through `f^(k+1)`
--     via `lie_e_pow_succ_toEnd_f`, pulling out a scalar and applying the IH.
-- Combinator: `induction k` after intros.
theorem s9934 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R))
    (k : ℕ),
  ((LieModule.toEnd R L M e) ^ (k + 1)) (((LieModule.toEnd R L M f) ^ k) v) = 0  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv k
  induction k with
  | zero => exact e_pow_succ_kills_f_pow_v_base R L M t hv
  | succ k ih => exact e_pow_succ_kills_f_pow_v_step R L M t hv k ih

end Problems.sl2_v_n_irreducible
