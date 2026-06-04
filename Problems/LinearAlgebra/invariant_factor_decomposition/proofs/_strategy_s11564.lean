import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_monic_directsum_of_torsion

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Reduce to the abstract monic structure theorem for finite torsion K[X]-modules.
-- `Module.AEval' T` is a finitely-generated torsion K[X]-module: torsion comes from
-- `Module.AEval.isTorsion_of_finiteDimensional`, finiteness is the standard AEval instance.
-- The whole remaining content (mathlib's `equiv_directSum_of_isTorsion` upgraded so the prime
-- generators are *monic* irreducibles) lives in the single abstract sub-goal
-- `monic_directsum_of_torsion`. Instances are supplied explicitly to dodge the `AEval'`
-- AddCommGroup/Module/Finite synthesis diamond.
theorem s11564 {K : Type u} [Field K] {V : Type*}
    [AddCommGroup V] [Module K V] [FiniteDimensional K V] (T : V →ₗ[K] V) :
    ∃ (ι : Type u) (_ : Fintype ι) (p : ι → Polynomial K) (_ : ∀ i, Irreducible (p i))
      (_ : ∀ i, (p i).Monic) (e : ι → ℕ),
      Nonempty (Module.AEval' T ≃ₗ[Polynomial K]
        DirectSum ι (fun i => Polynomial K ⧸ Submodule.span (Polynomial K) {p i ^ e i}))  := by
  exact @monic_directsum_of_torsion K _ (Module.AEval' T)
    (inferInstanceAs (AddCommGroup (Module.AEval' T)))
    (inferInstanceAs (Module (Polynomial K) (Module.AEval' T)))
    (inferInstanceAs (Module.Finite (Polynomial K) (Module.AEval K V T)))
    (Module.AEval.isTorsion_of_finiteDimensional K V T)

end Problems.LinearAlgebra.invariant_factor_decomposition
