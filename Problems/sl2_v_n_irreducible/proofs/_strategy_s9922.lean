import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_exists_e_pow_eq_scalar_v
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_apply_mem_w

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Decompose w ∈ W (W ≤ lieSpan {v}, w ≠ 0) into: pick k, λ with λ ≠ 0 and
-- eᵏ·w = λ•v (the substantive Humphreys "highest-power-of-f" extraction on
-- the cyclic span), and a structural step that any iterated e-action on a
-- W-element stays in W. Combinator: rewrite the e-power as λ•v and conclude.
-- sub1 (e_pow_apply_mem_w): purely structural — W is closed under repeated
--   bracketing with e ∈ t.toLieSubalgebra; induction on k. No sl₂ content.
-- sub2 (exists_e_pow_eq_scalar_v): the algebraic core — uses _hWle to push w
--   into lieSpan {v}, expands in {fⁱ·v}, and applies eᵏ at the top index.
theorem s9922 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0),
  ∃ (lam : R), lam ≠ 0 ∧ lam • v ∈ W  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne w hwW hwne
  have h_pow_mem :=
    e_pow_apply_mem_w R L M t hv hvne W hWle hWne w hwW hwne
  obtain ⟨k, lam, hlam_ne, hek⟩ :=
    exists_e_pow_eq_scalar_v R L M t hv hvne W hWle hWne w hwW hwne
  refine ⟨lam, hlam_ne, ?_⟩
  rw [← hek]
  exact h_pow_mem k

end Problems.sl2_v_n_irreducible
