import Mathlib
import Problems.sl2_v_n_irreducible.Defs

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- exists_idx_nonzero_of_sum_ne_zero: contrapositive — if all coefficients for i ≤ n are zero
-- then the sum vanishes, contradicting _hsumne; Finset.sum_eq_zero closes each summand.
theorem exists_idx_nonzero_of_sum_ne_zero : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0)
    (c : ℕ → R)
    (_hsumne : (∑ i ∈ Finset.range (n + 1), c i • ((LieModule.toEnd R L M f) ^ i) v) ≠ 0),
  ∃ i ≤ n, c i ≠ 0 := by
  intro R _ _ L _ _ M _ _ _ _ _ _ _ _ t _ n _ _ W _ _ _ _ _ c _hsumne
  by_contra hall
  push Not at hall
  apply _hsumne
  apply Finset.sum_eq_zero
  intro i hi
  simp only [Finset.mem_range] at hi
  have hin : i ≤ n := Nat.lt_succ_iff.mp hi
  rw [hall i hin]
  simp

end Problems.sl2_v_n_irreducible
