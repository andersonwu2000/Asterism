import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- e_pow_apply_mem_w: iterated e-action preserves W via LieSubmodule closure and induction on k
-- Induct on k; base is trivial. For succ: unfold e^(k+1) = e ∘ e^k using pow_succ' +
-- Module.End.mul_apply + toEnd_apply_apply, then use that e ∈ t.toLieSubalgebra R and
-- W is closed under bracketing with any element of that subalgebra (W.lie_mem).
theorem e_pow_apply_mem_w : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0) (k : ℕ),
  ((LieModule.toEnd R L M e) ^ k) w ∈ W := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n _hv _hvne W _hWle _hWne w _hwW _hwne k
  induction k with
  | zero => simpa using _hwW
  | succ k ih =>
    have he_mem : e ∈ t.toLieSubalgebra R := by
      rw [IsSl2Triple.mem_toLieSubalgebra_iff]
      exact ⟨1, 0, 0, by simp⟩
    rw [pow_succ', Module.End.mul_apply, LieModule.toEnd_apply_apply]
    change ⁅(⟨e, he_mem⟩ : t.toLieSubalgebra R), ((LieModule.toEnd R L M e ^ k) w)⁆ ∈ W
    exact W.lie_mem ih

end Problems.sl2_v_n_irreducible
