import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_bracket_l_pow_f_v_mem

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

-- Reduce sl₂-invariance of an arbitrary span-element y to the basis case:
--   sub1 (bracket_l_pow_f_v_mem): the substantive content — bracketing l with the
--     specific basis vector fⁱ·v lands in the span. (Handles unpacking
--     l = c₁·e + c₂·f + c₃·h via `mem_toLieSubalgebra_iff`, then each generator
--     case follows from the `Sl2.lie_*_pow_toEnd_f` API.)
-- Combinator: `Submodule.span_induction` on `_hy`; the basis case dispatches
-- to sub1, while zero/add/smul follow from `Submodule.{zero_mem,add_mem,smul_mem}`
-- combined with `lie_zero`, `lie_add`, `lie_smul`.
theorem s9931 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (_hv : t.HasPrimitiveVectorWith v (n : R)) (_hvne : v ≠ 0)
    (W : LieSubmodule R (t.toLieSubalgebra R) M)
    (_hWle : W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v})
    (_hWne : W ≠ ⊥)
    (w : M) (_hwW : w ∈ W) (_hwne : w ≠ 0)
    (l : (t.toLieSubalgebra R)) (y : M)
    (_hy : y ∈ Submodule.span R
      ((fun i => ((LieModule.toEnd R L M f) ^ i) v) '' (Finset.range (n + 1) : Set ℕ))),
  ⁅l, y⁆ ∈ Submodule.span R
    ((fun i => ((LieModule.toEnd R L M f) ^ i) v) '' (Finset.range (n + 1) : Set ℕ))  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne w hwW hwne l y hy
  have h_pow := bracket_l_pow_f_v_mem R L M t hv hvne W hWle hWne w hwW hwne l

  induction hy using Submodule.span_induction with
  | mem z hz =>
      obtain ⟨i, hi, rfl⟩ := hz
      rw [Finset.coe_range, Set.mem_Iio] at hi
      exact h_pow i hi
  | zero => simpa using Submodule.zero_mem _
  | add a b _ _ ha hb => simpa [lie_add] using Submodule.add_mem _ ha hb
  | smul r y _ hy => simpa [lie_smul] using Submodule.smul_mem _ r hy

end Problems.sl2_v_n_irreducible

