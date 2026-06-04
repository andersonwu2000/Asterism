import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- e_pow_succ_kills_f_pow_v_base: base case k=0; e kills the primitive vector v directly from
-- HasPrimitiveVectorWith.lie_e, after reducing e^1(f^0 v) to ⁅e, v⁆ via toEnd API.
theorem e_pow_succ_kills_f_pow_v_base : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)),
  ((LieModule.toEnd R L M e) ^ (0 + 1)) (((LieModule.toEnd R L M f) ^ 0) v) = 0 := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv
  simp only [zero_add, pow_one, pow_zero]
  rw [Module.End.one_apply, LieModule.toEnd_apply_apply]
  exact hv.lie_e

end Problems.sl2_v_n_irreducible
