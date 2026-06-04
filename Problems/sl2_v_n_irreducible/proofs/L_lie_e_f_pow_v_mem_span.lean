import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- lie_e_f_pow_v_mem_span: ⁅e, fⁱ·v⁆ lies in the span of {fʲ·v | j < n+1}
-- Case i=0: primitive vector condition gives ⁅e,v⁆=0. Case i=k+1: HasPrimitiveVectorWith.
-- lie_e_pow_succ_toEnd_f gives ⁅e,f^(k+1)·v⁆ = scalar · f^k·v, which is in the span.
theorem lie_e_f_pow_v_mem_span : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0) (i : ℕ) (_hi : i < n + 1),
  ⁅e, ((LieModule.toEnd R L M f) ^ i) v⁆ ∈ Submodule.span R
    ((fun i => ((LieModule.toEnd R L M f) ^ i) v) '' (Finset.range (n + 1) : Set ℕ)) := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n _hv _hvne W _hWle _hWne w _hwW _hwne i _hi
  rcases i with _ | k
  · simp only [pow_zero, Module.End.one_apply]
    rw [_hv.lie_e]
    exact Submodule.zero_mem _
  · have hk : k < n + 1 := by omega
    have hmem : ((LieModule.toEnd R L M f) ^ k) v ∈
      (fun i => ((LieModule.toEnd R L M f) ^ i) v) '' (Finset.range (n + 1) : Set ℕ) :=
      ⟨k, Finset.mem_coe.mpr (Finset.mem_range.mpr hk), rfl⟩
    rw [_hv.lie_e_pow_succ_toEnd_f k]
    exact Submodule.smul_mem _ _ (Submodule.subset_span hmem)

end Problems.sl2_v_n_irreducible
