import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_lie_span_v_subset_pow_f_span
import Problems.sl2_v_n_irreducible.proofs.L_mem_pow_f_span_exists_finset_sum

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Cyclicity of `lieSpan {v}` is bridged through the underlying R-submodule
-- spanned by `{v, f·v, …, fⁿ·v}` (which is sl₂-stable, so contains lieSpan {v}).
--   sub1 (lie_span_v_subset_pow_f_span): every element of the lieSpan lies in
--     this R-span (the substantive sl₂-invariance argument).
--   sub2 (mem_pow_f_span_exists_finset_sum): pure linear algebra unpacking of
--     R-span membership into a Finset.range (n+1)-indexed coefficient sum.
-- Combinator: push w through `_hWle` to land in `lieSpan {v}`, hit sub1, hit sub2.
theorem s9924 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0),
  ∃ (c : ℕ → R),
    w = ∑ i ∈ Finset.range (n + 1), c i • ((LieModule.toEnd R L M f) ^ i) v  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne w hwW hwne
  have hw_lie : w ∈ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v} := hWle hwW
  have h1 :=
    lie_span_v_subset_pow_f_span R L M t hv hvne W hWle hWne w hwW hwne w hw_lie
  exact
    mem_pow_f_span_exists_finset_sum R L M t hv hvne W hWle hWne w hwW hwne w h1
end Problems.sl2_v_n_irreducible
