import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_finset_sum_eq_scalar_v
import Problems.sl2_v_n_irreducible.proofs.L_mem_lie_span_v_exists_finset_sum

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Decompose the e-power extraction on a cyclic-span element into:
--   sub1 (mem_lie_span_v_exists_finset_sum): any w in `lieSpan {v}` admits an
--     expansion `w = Σ_{i ≤ n} c i • fⁱ v` (since fᵏ·v = 0 past k = n).
--   sub2 (e_pow_finset_sum_eq_scalar_v): applying eᵏ at the top nonzero index
--     of such a sum collapses it to a nonzero scalar multiple of v
--     (descent formula `lie_e_pow_succ_toEnd_f`).
-- Combinator: push w through `_hWle` into lieSpan, rewrite via sub1, apply sub2.
theorem s9923 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0),
  ∃ (k : ℕ) (lam : R), lam ≠ 0 ∧ ((LieModule.toEnd R L M e) ^ k) w = lam • v  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne w hwW hwne
  obtain ⟨c, hc⟩ :=
    mem_lie_span_v_exists_finset_sum R L M t hv hvne W hWle hWne w hwW hwne
  have hsumne :
      (∑ i ∈ Finset.range (n + 1), c i • ((LieModule.toEnd R L M f) ^ i) v) ≠ 0 := by
    rw [← hc]; exact hwne
  obtain ⟨k, lam, hlam, hk⟩ :=
    e_pow_finset_sum_eq_scalar_v R L M t hv hvne W hWle hWne w hwW hwne c hsumne
  refine ⟨k, lam, hlam, ?_⟩
  rw [hc]; exact hk
