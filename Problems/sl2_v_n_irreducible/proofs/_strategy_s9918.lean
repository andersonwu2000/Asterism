import Mathlib
import Problems.sl2_v_n_irreducible.Defs

namespace Problems.sl2_v_n_irreducible

-- Direct proof by induction on `m`: discard unused W/w/α context, then
-- `Nat.rec`. Base case `m = 0` is `simp` (empty product = 1, identity
-- endomorphism). Step case `k → k+1` uses `pow_succ` to peel one factor
-- of `toEnd e` off the outside, `toEnd_apply_apply` to expose `⁅e, ·⁆`,
-- `hv.lie_e_pow_succ_toEnd_f k` for the descent
-- `⁅e, fᵏ⁺¹·v⁆ = ((k+1)(n-k)) • fᵏ·v`, `map_smul` to pull the scalar
-- past `(toEnd e)ᵏ`, the IH on `k ≤ n` (from `Nat.le_of_succ_le hmn`),
-- and `Finset.prod_range_succ` + `mul_comm` to merge the new factor
-- onto the product. Sorry-free — no sub-goal files needed.
theorem s9918
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
    ((LieModule.toEnd R L M e) ^ m) (((LieModule.toEnd R L M f) ^ m) v)
      = (∏ i ∈ Finset.range m, ((i + 1 : R) * ((n : R) - i))) • v  := by
  clear hwW hwne hwspan hαm
  clear α
  induction m with
  | zero => simp
  | succ k ih =>
      have ihk := ih (Nat.le_of_succ_le hmn)
      rw [pow_succ, Module.End.mul_apply, LieModule.toEnd_apply_apply,
          hv.lie_e_pow_succ_toEnd_f k, map_smul, ihk, smul_smul,
          Finset.prod_range_succ, mul_comm]

end Problems.sl2_v_n_irreducible
