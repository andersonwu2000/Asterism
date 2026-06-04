import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- lie_f_f_pow_v_mem_span: ⁅f, fⁱ·v⁆ = f^(i+1)·v lies in span{fʲ·v | j < n+1}
-- Uses lie_f_pow_toEnd_f to rewrite the bracket, then shows f^(i+1)·v is in the
-- image (if i+1 < n+1) or equals 0 via pow_toEnd_f_eq_zero_of_eq_nat (if i = n).
theorem lie_f_f_pow_v_mem_span : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0) (i : ℕ) (_hi : i < n + 1),
  ⁅f, ((LieModule.toEnd R L M f) ^ i) v⁆ ∈ Submodule.span R
    ((fun i => ((LieModule.toEnd R L M f) ^ i) v) '' (Finset.range (n + 1) : Set ℕ)) := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n _hv _hvne W _hWle _hWne w _hwW _hwne i _hi
  rw [_hv.lie_f_pow_toEnd_f i]
  by_cases hi' : i + 1 < n + 1
  · apply Submodule.subset_span
    exact ⟨i + 1, by simp [hi'], rfl⟩
  · push Not at hi'
    have hin : i = n := by omega
    subst hin
    haveI : IsDomain R := inferInstance
    haveI : IsNoetherian R M := inferInstance
    haveI : IsTorsionFree R M := inferInstance
    rw [_hv.pow_toEnd_f_eq_zero_of_eq_nat (hn := rfl)]
    exact Submodule.zero_mem _

end Problems.sl2_v_n_irreducible
