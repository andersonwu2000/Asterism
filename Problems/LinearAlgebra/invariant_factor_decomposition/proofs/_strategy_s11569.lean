import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- K[X]-linear Chinese Remainder iso, proved directly (leaf, no sub-goals).
-- Cite mathlib's ring-level CRT `Ideal.quotientInfRingEquivPiQuotient` (coprimality of
-- the principal ideals from `Ideal.isCoprime_span_singleton_iff` on `hg`), then upgrade
-- that `≃+*` to `≃ₗ[K[X]]` by supplying `map_smul'`: on a representative `mk a` both
-- sides reduce to `fun i => mk (r * a)`, so `rfl` after `ext i`.
theorem s11569
    {K : Type*} [Field K] {ι : Type*} [Fintype ι] [DecidableEq ι]
    (g : ι → Polynomial K) (hg : ∀ i j, i ≠ j → IsCoprime (g i) (g j)) :
    Nonempty (
      (Polynomial K ⧸ ⨅ i, Submodule.span (Polynomial K) {g i})
        ≃ₗ[Polynomial K]
      (∀ i, Polynomial K ⧸ Submodule.span (Polynomial K) {g i}))  := by
  classical
  refine ⟨{ Ideal.quotientInfRingEquivPiQuotient
      (fun i => Submodule.span (Polynomial K) {g i})
      (fun i j hij => (Ideal.isCoprime_span_singleton_iff _ _).mpr (hg i j hij)) with
    map_smul' := ?_ }⟩
  intro r x
  obtain ⟨a, rfl⟩ := Ideal.Quotient.mk_surjective x
  ext i
  rfl

end Problems.LinearAlgebra.invariant_factor_decomposition
