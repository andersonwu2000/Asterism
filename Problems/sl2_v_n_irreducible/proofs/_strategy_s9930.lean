import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_succ_kills_f_pow_v

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Reduce `e^j (f^i v) = 0` (for `i < j`) to the single descent fact
-- `e^(i+1) (f^i v) = 0`. Combinator: factor `j = (j-(i+1)) + (i+1)` via
-- `pow_add` + `Module.End.mul_apply`, then close with `map_zero`.
theorem s9930 : ∀ (R : Type*) [Field R] [CharZero R]
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
    (_hcabove : ∀ i, j < i → i ≤ n → c i = 0)
    (i : ℕ) (_hilt : i < j),
  ((LieModule.toEnd R L M e) ^ j) (((LieModule.toEnd R L M f) ^ i) v) = 0  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne w hwW hwne
    c hsumne j hjle hcjne hcabove i hilt
  have h_succ_kills :=
    e_pow_succ_kills_f_pow_v R L M t hv hvne W hWle hWne w hwW hwne
      c hsumne j hjle hcjne hcabove i hilt
  have hjeq : j = (j - (i + 1)) + (i + 1) := by omega
  rw [hjeq, pow_add, Module.End.mul_apply, h_succ_kills, map_zero]

end Problems.sl2_v_n_irreducible
