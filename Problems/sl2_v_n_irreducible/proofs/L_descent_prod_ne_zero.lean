import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- descent_prod_ne_zero: product ∏ i < j, (i+1)*(n-i) is nonzero in CharZero field when j ≤ n
-- Each factor (i+1)*(n-i) is nonzero: (i+1) ≥ 1 and (n-i) ≥ 1 when i < j ≤ n, both
-- cast via Nat.cast_ne_zero in CharZero; Finset.prod_ne_zero_iff reduces to pointwise.
theorem descent_prod_ne_zero : ∀ (R : Type*) [Field R] [CharZero R]
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
  (∏ i ∈ Finset.range j, (((i:R) + 1) * ((n : R) - i))) ≠ 0 := by
  intro R _ _ L _ _ M _ _ _ _ _ _ _ _ t _ n _ _ _ _ _ _ _ _ c _ j _hjle _ _
  rw [Finset.prod_ne_zero_iff]
  intro i hi
  simp only [Finset.mem_range] at hi
  apply mul_ne_zero
  · have : (i : R) + 1 = ((i + 1 : ℕ) : R) := by push_cast; ring
    rw [this]
    exact_mod_cast Nat.succ_ne_zero i
  · have hilt : i < n := Nat.lt_of_lt_of_le hi _hjle
    have hle : i ≤ n := Nat.le_of_lt hilt
    have : (n : R) - (i : R) = ((n - i : ℕ) : R) := by rw [Nat.cast_sub hle]
    rw [this]
    exact_mod_cast Nat.sub_ne_zero_of_lt hilt

end Problems.sl2_v_n_irreducible
