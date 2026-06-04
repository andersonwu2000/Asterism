import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- v_mem_pow_f_span: v = f^0·v lies in Submodule.span R {f^i·v | i < n+1}
-- Base case: apply Submodule.subset_span, then witness i=0 via Finset.mem_range.
theorem v_mem_pow_f_span : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0),
  v ∈ Submodule.span R
    ((fun i => ((LieModule.toEnd R L M f) ^ i) v) '' (Finset.range (n + 1) : Set ℕ)) := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n _hv _hvne W _hWle _hWne w _hwW _hwne
  apply Submodule.subset_span
  simp only [Set.mem_image, Finset.mem_coe, Finset.mem_range]
  exact ⟨0, Nat.succ_pos n, by simp⟩

end Problems.sl2_v_n_irreducible
