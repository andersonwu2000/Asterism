import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Drop the subsingleton (¬P) summands: the inclusion {i//P i} ↪ I induces a linear
-- equivalence because every dropped summand M i is a subsingleton (hence 0).
-- F restricts a sum to its P-components, G includes the subtype components back; the
-- two round-trips close componentwise (toModule_lof), the ¬P case via Subsingleton.elim.
theorem s11586 {R : Type*} [CommRing R]
    {I : Type*} [Fintype I] [DecidableEq I]
    (M : I → Type*) [∀ i, AddCommGroup (M i)] [∀ i, Module R (M i)]
    (P : I → Prop) [DecidablePred P]
    (htriv : ∀ i, ¬ P i → Subsingleton (M i)) :
    Nonempty (DirectSum I M ≃ₗ[R] DirectSum {i // P i} (fun i => M i.val))  := by
  classical
  let F : DirectSum I M →ₗ[R] DirectSum {i // P i} (fun i => M i.val) :=
    DirectSum.toModule R I _ (fun i =>
      if h : P i then DirectSum.lof R {i // P i} (fun i => M i.val) ⟨i, h⟩ else 0)
  let G : DirectSum {i // P i} (fun i => M i.val) →ₗ[R] DirectSum I M :=
    DirectSum.toModule R {i // P i} _ (fun j => DirectSum.lof R I M j.val)
  refine ⟨LinearEquiv.ofLinear F G ?_ ?_⟩
  · apply DirectSum.linearMap_ext
    rintro ⟨i, hi⟩
    apply LinearMap.ext
    intro x
    simp only [F, G, LinearMap.comp_apply, DirectSum.toModule_lof, LinearMap.id_apply, dif_pos hi]
  · apply DirectSum.linearMap_ext
    intro i
    apply LinearMap.ext
    intro x
    simp only [LinearMap.comp_apply, LinearMap.id_apply]
    by_cases hi : P i
    · simp only [F, G, DirectSum.toModule_lof, dif_pos hi]
    · have : Subsingleton (M i) := htriv i hi
      rw [Subsingleton.elim x 0]
      simp only [F, G, map_zero]

end Problems.LinearAlgebra.invariant_factor_decomposition
