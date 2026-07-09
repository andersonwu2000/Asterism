import Mathlib

/-!
# Primary decomposition over a polynomial ring

This file establishes the primary decomposition of a finitely generated torsion module over the
polynomial ring `K[X]`, where `K` is a field. The central result `monic_directsum_of_torsion`
upgrades Mathlib's `Module.equiv_directSum_of_isTorsion` so that every cyclic summand
`K[X]/(p_i ^ e_i)` carries a **monic** irreducible generator. The specialisation `primary_form`
applies this to a finite-dimensional `K`-vector space equipped with a linear operator, yielding
the primary decomposition underlying the rational canonical / Jordan normal form theory.
-/

namespace Library.LinearAlgebra.InvariantFactor.PrimaryDecomposition

/-- Given an irreducible polynomial `a` over a field `K` and a natural number `n`, there exists a
monic irreducible polynomial `q` — a normalized associate of `a` — such that `K[X] ⧸ (a ^ n)` and
`K[X] ⧸ (q ^ n)` are isomorphic as `K[X]`-modules. -/
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

section PrimaryDecomp

variable {K : Type u} [Field K]

/-- Every finitely generated torsion module over `K[X]` decomposes as a direct sum of cyclic
modules `K[X] ⧸ (p_i ^ e_i)` with each `p_i` a monic irreducible polynomial. This sharpens
`Module.equiv_directSum_of_isTorsion`, which produces irreducible but not necessarily monic
generators. -/
theorem monic_directsum_of_torsion {M : Type*}
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

/-- For any linear operator `T` on a finite-dimensional `K`-vector space `V`, the associated
`K[X]`-module `Module.AEval' T` decomposes as a direct sum of cyclic modules
`K[X] ⧸ (p_i ^ e_i)` with monic irreducible `p_i`. This is the primary decomposition of the
operator `T`. -/
theorem primary_form {V : Type*}
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

end PrimaryDecomp

end Library.LinearAlgebra.InvariantFactor.PrimaryDecomposition
