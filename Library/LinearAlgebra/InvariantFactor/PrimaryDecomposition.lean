import Mathlib

namespace Library.LinearAlgebra.InvariantFactor.PrimaryDecomposition

-- Take q := normalize a, the monic associate of the irreducible a.
-- It is irreducible (associated to a) and monic; since a^n and q^n are associated,
-- their generated spans coincide, so the quotients are equal — Submodule.quotEquivOfEq
-- supplies the K[X]-linear iso. Direct leaf proof, no sub-goals.
theorem exists_monic_quot_equiv {K : Type*} [Field K] (a : Polynomial K)
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

-- Upgrade mathlib's prime-power torsion decomposition to *monic* irreducible generators.
-- `Module.equiv_directSum_of_isTorsion` gives the decomposition with irreducible (not nec.
-- monic) generators `p i`; for each, `exists_monic_quot_equiv` produces a monic irreducible
-- associate `q i` together with a quotient linear-equiv (spans of `a^e` and `q^e` agree).
-- `choose` extracts the family `q`, and `DirectSum.congrLinearEquiv` transports the direct
-- sum component-wise.
theorem monic_directsum_of_torsion {K : Type u} [Field K] {M : Type*}
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

-- Reduce to the abstract monic structure theorem for finite torsion K[X]-modules.
-- `Module.AEval' T` is a finitely-generated torsion K[X]-module: torsion comes from
-- `Module.AEval.isTorsion_of_finiteDimensional`, finiteness is the standard AEval instance.
-- The whole remaining content (mathlib's `equiv_directSum_of_isTorsion` upgraded so the prime
-- generators are *monic* irreducibles) lives in the single abstract sub-goal
-- `monic_directsum_of_torsion`. Instances are supplied explicitly to dodge the `AEval'`
-- AddCommGroup/Module/Finite synthesis diamond.
theorem primary_form {K : Type u} [Field K] {V : Type*}
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

end Library.LinearAlgebra.InvariantFactor.PrimaryDecomposition
