import Mathlib
import Problems.sl2_v_n_irreducible.Defs

namespace Problems.sl2_v_n_irreducible

-- e_pow_kills_lower_fpow_v: e^j annihilates f^i·v for i < j via sl₂ recursion on i
-- Base: e·v = 0 (primitive vector). Step: e(f^(i+1)·v) = c·f^i·v, then IH on f^i·v.
theorem e_pow_kills_lower_fpow_v
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
    ∀ i j : ℕ, i < j →
      ((LieModule.toEnd R L M e) ^ j) (((LieModule.toEnd R L M f) ^ i) v) = 0 := by
    intro i
    induction i with
    | zero =>
      intro j hj
      simp only [pow_zero, Module.End.one_apply]
      cases j with
      | zero => exact absurd hj (Nat.not_lt_zero 0)
      | succ j' =>
        rw [pow_succ, Module.End.mul_apply]
        simp [LieModule.toEnd_apply_apply, hv.lie_e]
    | succ i' ih =>
      intro j hj
      cases j with
      | zero => exact absurd hj (Nat.not_lt_zero _)
      | succ j' =>
        rw [pow_succ, Module.End.mul_apply]
        have key : (LieModule.toEnd R L M e) (((LieModule.toEnd R L M f) ^ (i' + 1)) v) =
                   (((i' : R) + 1) * ((n : R) - (i' : R))) •
                     ((LieModule.toEnd R L M f) ^ i') v := by
          rw [LieModule.toEnd_apply_apply]; exact hv.lie_e_pow_succ_toEnd_f i'
        rw [key, map_smul]; simp [ih j' (Nat.lt_of_succ_lt_succ hj)]

end Problems.sl2_v_n_irreducible
