import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- lie_h_f_pow_v_mem_span: h-action on fⁱv lies in the span via lie_h_pow_toEnd_f scalar formula
theorem lie_h_f_pow_v_mem_span : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0) (i : ℕ) (_hi : i < n + 1),
  ⁅h, ((LieModule.toEnd R L M f) ^ i) v⁆ ∈ Submodule.span R
    ((fun i => ((LieModule.toEnd R L M f) ^ i) v) '' (Finset.range (n + 1) : Set ℕ)) := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n _hv _hvne W _hWle _hWne w _hwW _hwne i _hi
  rw [_hv.lie_h_pow_toEnd_f i]
  apply Submodule.smul_mem
  apply Submodule.subset_span
  exact ⟨i, Finset.mem_coe.mpr (Finset.mem_range.mpr _hi), rfl⟩

end Problems.sl2_v_n_irreducible
