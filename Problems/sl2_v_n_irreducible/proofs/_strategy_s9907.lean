import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_exists_nonzero_scalar_v_in_w
import Problems.sl2_v_n_irreducible.proofs.L_v_of_scalar_v_mem

namespace Problems.sl2_v_n_irreducible

-- Reduce v ∈ W to (∃ c ≠ 0, c • v ∈ W) ∧ (LieSubmodule scalar inverse).
-- Sub-goal A carries the substantive e-descent argument (largest f-power → eᵐ
-- applied gives a nonzero scalar multiple of v in W). Sub-goal B is the generic
-- "scalar-divide" step in any LieSubmodule over a Field: c⁻¹ • (c • v) = v.
theorem s9907 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0),
  ∀ (W : LieSubmodule R (t.toLieSubalgebra R) M),
    W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v} →
    W ≠ ⊥ → v ∈ W  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hW hne
  have hA := exists_nonzero_scalar_v_in_w R L M t hv hvne W hW hne
  have hB := v_of_scalar_v_mem R L M t hv hvne W
  obtain ⟨c, hc, hcv⟩ := hA
  exact hB c hc hcv

end Problems.sl2_v_n_irreducible
