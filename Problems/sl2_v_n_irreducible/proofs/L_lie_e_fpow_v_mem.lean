import Mathlib
import Problems.sl2_v_n_irreducible.Defs

namespace Problems.sl2_v_n_irreducible

-- lie_e_fpow_v_mem: HasPrimitiveVectorWith.lie_e_pow_succ_toEnd_f gives ⁅e, fᵏ·v⁆ as a
-- scalar multiple of fᵏ⁻¹·v, which is in the span; the k=0 base uses hv.lie_e = 0.
theorem lie_e_fpow_v_mem
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R))
    (k : ℕ) :
    ⁅e, ((LieModule.toEnd R L M f) ^ k) v⁆ ∈
      Submodule.span R (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v)) := by
  cases k with
  | zero =>
    simp only [pow_zero, Module.End.one_apply]
    rw [hv.lie_e]
    exact Submodule.zero_mem _
  | succ k' =>
    rw [hv.lie_e_pow_succ_toEnd_f k']
    apply Submodule.smul_mem
    apply Submodule.subset_span
    exact Set.mem_range.mpr ⟨k', rfl⟩

end Problems.sl2_v_n_irreducible
