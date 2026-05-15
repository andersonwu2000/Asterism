import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_descfact_ne_zero
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_fpow_eq_descfact_v

namespace Problems.sl2_v_n_irreducible

-- Closed-form: e^m·f^m·v equals the descending-factorial scalar (∏ (i+1)(n−i)) • v.
-- Sub-goal A `e_pow_fpow_eq_descfact_v`: the explicit equation (induction on m using
-- Mathlib's `IsSl2Triple.HasPrimitiveVectorWith.lie_e_pow_succ_toEnd_f` descent step).
-- Sub-goal B `descfact_ne_zero`: each factor (i+1)(n-i) is a positive Nat cast in CharZero R
-- (uses `hmn : m ≤ n` to keep n-i strictly positive for i < m).
-- Combinator: refine ⟨_, h_ne, h_eq⟩ on the existential.
theorem s9916
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
    ∃ c : R, c ≠ 0 ∧
      ((LieModule.toEnd R L M e) ^ m) (((LieModule.toEnd R L M f) ^ m) v) = c • v  := by
  have h_eq :=
    e_pow_fpow_eq_descfact_v R L M t hv hvne W hWle w hwW hwne hwspan m hmn α hαm
  have h_ne :=
    descfact_ne_zero R L M t hv hvne W hWle w hwW hwne hwspan m hmn α hαm
  exact ⟨_, h_ne, h_eq⟩

end Problems.sl2_v_n_irreducible
