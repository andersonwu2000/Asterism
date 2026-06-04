import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_exists_top_nonzero_coeff
import Problems.sl2_v_n_irreducible.proofs.L_e_pow_top_eq_scalar_v

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Decompose the e-power extraction on a Σ c_i • f^i v sum into:
--   sub1 (exists_top_nonzero_coeff): from S ≠ 0, pick the largest j ≤ n with
--     c j ≠ 0 (and c i = 0 for j < i ≤ n). Pure finite-support combinatorics
--     combined with linear independence of {f^i v}_{i ≤ n}; no descent content.
--   sub2 (e_pow_top_eq_scalar_v): with such j in hand, applying e^j to S yields
--     a nonzero scalar multiple of v. This is the substantive descent formula
--     (lie_e_pow_succ_toEnd_f): terms i < j vanish (highest-weight kill),
--     terms i > j are zero by hypothesis, and the i = j term lands on v.
-- Combinator: ⟨j, lam, hlam, heq⟩ assembled directly.
theorem s9925 : ∀ (R : Type*) [Field R] [CharZero R]
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
  ∃ (k : ℕ) (lam : R), lam ≠ 0 ∧
    ((LieModule.toEnd R L M e) ^ k)
        (∑ i ∈ Finset.range (n + 1), c i • ((LieModule.toEnd R L M f) ^ i) v)
      = lam • v  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne w hwW hwne c hsumne
  have h_top :=
    exists_top_nonzero_coeff R L M t hv hvne W hWle hWne w hwW hwne c hsumne
  obtain ⟨j, hjle, hcjne, hcabove⟩ := h_top
  have h_pow :=
    e_pow_top_eq_scalar_v R L M t hv hvne W hWle hWne w hwW hwne c hsumne j hjle hcjne hcabove
  obtain ⟨lam, hlamne, heq⟩ := h_pow
  exact ⟨j, lam, hlamne, heq⟩

end Problems.sl2_v_n_irreducible
