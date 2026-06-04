import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Take q := normalize a, the monic associate of the irreducible a.
-- It is irreducible (associated to a) and monic; since a^n and q^n are associated,
-- their generated spans coincide, so the quotients are equal — Submodule.quotEquivOfEq
-- supplies the K[X]-linear iso. Direct leaf proof, no sub-goals.
theorem s11567 {K : Type*} [Field K] (a : Polynomial K)
    (ha : Irreducible a) (n : ℕ) :
    ∃ q : Polynomial K, Irreducible q ∧ q.Monic ∧
      Nonempty ((Polynomial K ⧸ Submodule.span (Polynomial K) {a ^ n}) ≃ₗ[Polynomial K]
        (Polynomial K ⧸ Submodule.span (Polynomial K) {q ^ n}))  := by
  classical
  refine ⟨normalize a, (associated_normalize a).irreducible ha,
    Polynomial.monic_normalize ha.ne_zero, ?_⟩
  have hassoc : Associated (a ^ n) (normalize a ^ n) := (associated_normalize a).pow_pow
  have hspan : Submodule.span (Polynomial K) {a ^ n}
      = Submodule.span (Polynomial K) {normalize a ^ n} :=
    Ideal.span_singleton_eq_span_singleton.mpr hassoc
  exact ⟨Submodule.quotEquivOfEq _ _ hspan⟩

end Problems.LinearAlgebra.invariant_factor_decomposition
