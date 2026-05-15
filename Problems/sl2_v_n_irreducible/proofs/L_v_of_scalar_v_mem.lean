import Mathlib
import Problems.sl2_v_n_irreducible.Defs

namespace Problems.sl2_v_n_irreducible

-- v_of_scalar_v_mem: scalar-divide in a LieSubmodule over a Field;
-- if c ≠ 0 and c • v ∈ W then v = c⁻¹ • (c • v) ∈ W by smul closure.
theorem v_of_scalar_v_mem : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0),
  ∀ (W : LieSubmodule R (t.toLieSubalgebra R) M) (c : R),
    c ≠ 0 → c • v ∈ W → v ∈ W := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W c hc hmem
  have h1 : c⁻¹ • (c • v) ∈ W := W.smul_mem c⁻¹ hmem
  rwa [inv_smul_smul₀ hc] at h1

end Problems.sl2_v_n_irreducible
