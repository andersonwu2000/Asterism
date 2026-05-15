import Mathlib
import Problems.sl2_v_n_irreducible.Defs
import Problems.sl2_v_n_irreducible.proofs.L_descent_to_scalar_v
import Problems.sl2_v_n_irreducible.proofs.L_nonzero_of_ne_bot

namespace Problems.sl2_v_n_irreducible

-- Reduce ∃ c≠0, c•v ∈ W to (witness extraction) + (e-descent on a concrete element).
-- Sub-goal `nonzero_of_ne_bot` is a generic submodule fact (W ≠ ⊥ → ∃ w ∈ W, w ≠ 0).
-- Sub-goal `descent_to_scalar_v` carries the substantive Humphreys argument:
-- expand w in the {fᵏ·v} spanning set, take the largest non-vanishing power m,
-- and apply eᵐ to land on a non-zero scalar multiple of v inside W.
theorem s9908 : ∀ (R : Type*) [Field R] [CharZero R]
    (L : Type*) [LieRing L] [LieAlgebra R L]
    (M : Type*) [AddCommGroup M] [Module R M] [LieRingModule L M] [LieModule R L M]
    [Module.Finite R M] {h e f : L} (t : IsSl2Triple h e f)
    {v : M} {n : ℕ} (hv : t.HasPrimitiveVectorWith v (n : R)) (hvne : v ≠ 0),
  ∀ (W : LieSubmodule R (t.toLieSubalgebra R) M),
    W ≤ LieSubmodule.lieSpan R (t.toLieSubalgebra R) {v} →
    W ≠ ⊥ → ∃ c : R, c ≠ 0 ∧ c • v ∈ W  := by
  intro R _ _ L _ _ M _ _ _ _ _ h e f t v n hv hvne W hWle hWne
  have h_w := nonzero_of_ne_bot R L M t hv hvne W hWle hWne
  obtain ⟨w, hwW, hwne⟩ := h_w
  exact descent_to_scalar_v R L M t hv hvne W hWle w hwW hwne
end Problems.sl2_v_n_irreducible
