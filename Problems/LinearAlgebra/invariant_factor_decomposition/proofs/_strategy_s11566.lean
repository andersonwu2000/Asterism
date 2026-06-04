import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_exists_monic_quot_equiv

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Upgrade mathlib's prime-power torsion decomposition to *monic* irreducible generators.
-- `Module.equiv_directSum_of_isTorsion` gives the decomposition with irreducible (not nec.
-- monic) generators `p i`; for each, `exists_monic_quot_equiv` produces a monic irreducible
-- associate `q i` together with a quotient linear-equiv (spans of `a^e` and `q^e` agree).
-- `choose` extracts the family `q`, and `DirectSum.congrLinearEquiv` transports the direct
-- sum component-wise.
theorem s11566 {K : Type u} [Field K] {M : Type*}
    [AddCommGroup M] [Module (Polynomial K) M] [Module.Finite (Polynomial K) M]
    (hM : Module.IsTorsion (Polynomial K) M) :
    ∃ (ι : Type u) (_ : Fintype ι) (p : ι → Polynomial K) (_ : ∀ i, Irreducible (p i))
      (_ : ∀ i, (p i).Monic) (e : ι → ℕ),
      Nonempty (M ≃ₗ[Polynomial K]
        DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i}))  := by
  obtain ⟨ι, hfin, p, hp_irr, e, ⟨equiv⟩⟩ :=
    Module.equiv_directSum_of_isTorsion (R := Polynomial K) (M := M) hM
  choose q hq_irr hq_monic hq_equiv using
    fun i => exists_monic_quot_equiv (p i) (hp_irr i) (e i)
  refine ⟨ι, hfin, q, hq_irr, hq_monic, e, ?_⟩
  exact ⟨equiv.trans (DirectSum.congrLinearEquiv (fun i => (hq_equiv i).some))⟩



end Problems.LinearAlgebra.invariant_factor_decomposition
