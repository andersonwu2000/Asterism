import Mathlib
import Problems.sl2_v_n_irreducible.Defs

namespace Problems.sl2_v_n_irreducible

-- lie_f_fpow_v_mem: f·(fᵏ·v) = fᵏ⁺¹·v lies in span{fᵏ·v} via pow_succ' + toEnd_apply_apply
theorem lie_f_fpow_v_mem
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R))
    (k : ℕ) :
    ⁅f, ((LieModule.toEnd R L M f) ^ k) v⁆ ∈
      Submodule.span R (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v)) := by
  apply Submodule.subset_span
  exact ⟨k + 1, by simp [pow_succ', Module.End.mul_apply, LieModule.toEnd_apply_apply]⟩

end Problems.sl2_v_n_irreducible
