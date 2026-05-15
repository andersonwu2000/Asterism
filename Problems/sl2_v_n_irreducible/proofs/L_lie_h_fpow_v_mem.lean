import Mathlib
import Problems.sl2_v_n_irreducible.Defs

namespace Problems.sl2_v_n_irreducible

-- lie_h_fpow_v_mem: h-weight formula places ⁅h, fᵏ·v⁆ in the cyclic span as a scalar multiple
theorem lie_h_fpow_v_mem
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R))
    (k : ℕ) :
    ⁅h, ((LieModule.toEnd R L M f) ^ k) v⁆ ∈
      Submodule.span R (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v)) := by
  rw [hv.lie_h_pow_toEnd_f k]
  apply Submodule.smul_mem
  exact Submodule.subset_span (Set.mem_range.mpr ⟨k, rfl⟩)

end Problems.sl2_v_n_irreducible
