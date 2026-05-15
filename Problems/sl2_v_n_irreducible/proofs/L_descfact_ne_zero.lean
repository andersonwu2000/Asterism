import Mathlib
import Problems.sl2_v_n_irreducible.Defs

namespace Problems.sl2_v_n_irreducible

-- descfact_ne_zero: descending-factorial product is nonzero in CharZero field when m ≤ n,
-- since each factor (i+1)(n-i) has i+1 ≥ 1 > 0 and n-i ≥ 1 > 0 (from i < m ≤ n).
theorem descfact_ne_zero
    (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (w : M) (hwW : w ∈ W) (hwne : w ≠ 0)
    (hwspan : w ∈ Submodule.span R
      (Set.range (fun k : ℕ => ((LieModule.toEnd R L M f) ^ k) v)))
    (m : ℕ) (hmn : m ≤ n) (α : ℕ → R) (hαm : α m ≠ 0) :
    (∏ i ∈ Finset.range m, ((i + 1 : R) * ((n : R) - i))) ≠ 0 := by
  rw [Finset.prod_ne_zero_iff]
  intro i hi
  apply mul_ne_zero
  · exact_mod_cast Nat.succ_ne_zero i
  · have him : i < m := Finset.mem_range.mp hi
    have hin : i < n := Nat.lt_of_lt_of_le him hmn
    rw [sub_ne_zero]
    exact_mod_cast (Nat.ne_of_lt hin).symm

end Problems.sl2_v_n_irreducible
