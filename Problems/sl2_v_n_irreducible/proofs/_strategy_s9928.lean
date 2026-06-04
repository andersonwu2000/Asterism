import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_pow_f_span_bracket_closed
import Problems.sl2_v_n_irreducible.proofs.L_v_mem_pow_f_span

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Reduce sl₂-invariance of the cyclic span to an induction over lieSpan {v}:
--   sub1 (v_mem_pow_f_span): the base case v = f⁰·v ∈ Submodule.span R {fⁱ·v}.
--   sub2 (pow_f_span_bracket_closed): the substantive sl₂-invariance — bracketing
--     by any sl₂ element preserves membership in the R-span (h scales, e descends,
--     f raises with f^(n+1)·v = 0).
-- Combinator: induct on `_hxle` via `LieSubmodule.lieSpan_induction`; sub1 supplies
-- the singleton-mem base, sub2 the bracket case, and zero/add/smul are automatic
-- closure properties of `Submodule.span`.
theorem s9928 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0)
    (x : M) (_hxle : x ∈ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v}),
  x ∈ Submodule.span R
    ((fun i => ((LieModule.toEnd R L M f) ^ i) v) '' (Finset.range (n + 1) : Set ℕ))  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne w hwW hwne x hxle
  have h_v_mem := v_mem_pow_f_span R L M t hv hvne W hWle hWne w hwW hwne
  have h_bracket := pow_f_span_bracket_closed R L M t hv hvne W hWle hWne w hwW hwne
  induction hxle using LieSubmodule.lieSpan_induction with
  | mem y hy => rcases hy with rfl; exact h_v_mem
  | zero => exact Submodule.zero_mem _
  | add a b _ _ ha hb => exact Submodule.add_mem _ ha hb
  | smul r y _ hy => exact Submodule.smul_mem _ r hy
  | lie l y _ hy => exact h_bracket l y hy

end Problems.sl2_v_n_irreducible
