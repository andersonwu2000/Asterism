import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- e_pow_j_apply_f_pow_j_v_eq_prod: descent identity by induction on j using lie_e_pow_succ_toEnd_f
theorem e_pow_j_apply_f_pow_j_v_eq_prod : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0)
    (c : ℕ → R)
    (_hsumne : (∑ i ∈ Finset.range (n + 1), c i • ((LieModule.toEnd R L M f) ^ i) v) ≠ 0)
    (j : ℕ) (_hjle : j ≤ n) (_hcjne : c j ≠ 0)
    (_hcabove : ∀ i, j < i → i ≤ n → c i = 0),
  ((LieModule.toEnd R L M e) ^ j) (((LieModule.toEnd R L M f) ^ j) v)
    = (∏ i ∈ Finset.range j, (((i:R) + 1) * ((n : R) - i))) • v := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n _hv _hvne W _hWle _hWne w _hwW _hwne c _hsumne
    j _hjle _hcjne _hcabove
  suffices hkey : ∀ k : ℕ,
      ((LieModule.toEnd R L M e) ^ k) (((LieModule.toEnd R L M f) ^ k) v)
        = (∏ i ∈ Finset.range k, (((i : R) + 1) * ((n : R) - i))) • v from hkey j
  intro k
  induction k with
  | zero => simp
  | succ k ih =>
    rw [pow_succ, Module.End.mul_apply, LieModule.toEnd_apply_apply,
        _hv.lie_e_pow_succ_toEnd_f k, map_smul, ih, smul_smul, Finset.prod_range_succ]
    ring

end Problems.sl2_v_n_irreducible
