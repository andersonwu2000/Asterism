import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- e_pow_succ_kills_f_pow_v_step: peel one e via pow_succ+mul_apply, rewrite using
-- HasPrimitiveVectorWith.lie_e_pow_succ_toEnd_f to get a scalar multiple of f^k v,
-- then map_smul + IH + smul_zero closes the goal.
theorem e_pow_succ_kills_f_pow_v_step : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R))
    (k : ℕ)
    (_ih : ((LieModule.toEnd R L M e) ^ (k + 1)) (((LieModule.toEnd R L M f) ^ k) v) = 0),
  ((LieModule.toEnd R L M e) ^ (k + 1 + 1)) (((LieModule.toEnd R L M f) ^ (k + 1)) v) = 0 := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n _hv k _ih
  rw [pow_succ, Module.End.mul_apply, LieModule.toEnd_apply_apply]
  rw [_hv.lie_e_pow_succ_toEnd_f k]
  rw [map_smul, _ih, smul_zero]

end Problems.sl2_v_n_irreducible
