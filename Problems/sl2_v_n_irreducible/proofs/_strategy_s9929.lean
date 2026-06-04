import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_descent_prod_ne_zero
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_j_apply_f_pow_j_v_eq_prod

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Compute e^j (f^j v) explicitly using the sl₂ descent formula:
--   e^j (f^j v) = (∏ i ∈ range j, (i+1) * (n - i)) • v, and the product
--   is nonzero in CharZero whenever j ≤ n (each factor (i+1)(n-i) > 0 for i < j ≤ n).
-- sub1 (e_pow_j_apply_f_pow_j_v_eq_prod): the descent identity by induction on j,
--   stepping via lie_e_pow_succ_toEnd_f.
-- sub2 (descent_prod_ne_zero): the explicit product is nonzero (arithmetic in CharZero).
-- Combinator: existential witness μ := ∏..., sub2 supplies μ ≠ 0, sub1 supplies the equation.
theorem s9929 : ∀ (R : Type*) [Field R] [CharZero R]
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
  ∃ mu : R, mu ≠ 0 ∧
    ((LieModule.toEnd R L M e) ^ j) (((LieModule.toEnd R L M f) ^ j) v) = mu • v  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne w hwW hwne c hsumne j hjle hcjne hcabove
  have h_eq := e_pow_j_apply_f_pow_j_v_eq_prod R L M t hv hvne W hWle hWne w hwW hwne c hsumne j hjle hcjne hcabove
  have h_ne := descent_prod_ne_zero R L M t hv hvne W hWle hWne w hwW hwne c hsumne j hjle hcjne hcabove
  exact ⟨_, h_ne, h_eq⟩

end Problems.sl2_v_n_irreducible
