import Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexBasic

/-!
# The supported-subcomplex differential and the subspace comparison

This file identifies the differential of the "supported" subcomplex of the singular
chain complex of `X` on a subset `A` (as transported through the `Finsupp.supported` /
`Finsupp.supportedEquivFinsupp` identification) with the differential of the singular
chain complex of the subspace `A` itself, along the degreewise comparison
isomorphisms `subspace_supported_x_iso` from `SupportedSubcomplexBasic`.

## Main statements

* `subspace_supported_d_single`: on a single supported generator, the transported
  differential agrees with the alternating sum of faces computed in the subspace `A`.
* `subspace_supported_d_comm`: the degreewise comparison isomorphisms
  `subspace_supported_x_iso` intertwine the two differentials, i.e. they assemble
  into a chain map.

## Main definitions

* `subspace_supported_chain_complex_iso`: the resulting isomorphism between the
  supported subcomplex of `singular_subcomplex_of_set X A` and the singular chain
  complex of the subspace `A`.

## Implementation notes

`subspace_supported_d_comm` is kept as a standalone Prop so that
`subspace_supported_chain_complex_iso` can cite it when assembling the isomorphism via
`HomologicalComplex.Hom.isoOfComponents`, mirroring how the whole-space analogue
`chain_complex_top_iso` is built from `chain_complex_top_iso_comm`.
-/

open CategoryTheory Simplicial
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexBasic

namespace Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexDifferential

variable {R : Type} [Ring R] (X : TopCat.{0}) (A : Set X)

/-- On a single supported generator `⟨Finsupp.single ↑σ 1, hσ⟩`, the transported
differential of the supported subcomplex agrees with the alternating sum of faces
`∑ i, (-1) ^ i • Finsupp.single (δ i (bijection σ)) 1` computed directly in the
singular chain complex of the subspace `A`. -/
theorem subspace_supported_d_single (n : ℕ)
    (σ : ↥((singular_subcomplex_of_set X A).obj (Opposite.op (SimplexCategory.mk (n + 1)))))
    (hσ : (Finsupp.single (↑σ) 1 : _ →₀ R) ∈ Finsupp.supported R R
      ((singular_subcomplex_of_set X A).obj (Opposite.op (SimplexCategory.mk (n + 1))))) :
    subspace_supported_finsupp_equiv (R := R) X A n
        (ModuleCat.Hom.hom
          ((supported_chain_complex (R := R) (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A)).d (n + 1) n)
          ⟨Finsupp.single (↑σ) 1, hσ⟩)
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) •
          Finsupp.single ((TopCat.toSSet.obj (TopCat.of A)).δ i
            (subspace_supported_simplex_bijection X A (n + 1) σ)) 1 := by
  classical
  have hface : ∀ i : Fin (n + 2),
      (TopCat.toSSet.obj X).δ i (↑σ) ∈
        (singular_subcomplex_of_set X A).obj (Opposite.op (SimplexCategory.mk n)) :=
    fun i => (singular_subcomplex_of_set X A).map (SimplexCategory.δ i).op σ.2
  set τ : Fin (n + 2) →
      ↥((singular_subcomplex_of_set X A).obj (Opposite.op (SimplexCategory.mk n))) :=
    fun i => ⟨(TopCat.toSSet.obj X).δ i (↑σ), hface i⟩ with hτ
  have hsum :
      (ModuleCat.Hom.hom
          ((supported_chain_complex (R := R) (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A)).d (n + 1) n)
          ⟨Finsupp.single (↑σ) 1, hσ⟩)
        = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) •
            (⟨Finsupp.single (↑(τ i)) 1, Finsupp.single_mem_supported R 1 (τ i).2⟩ :
              Finsupp.supported R R
                ((singular_subcomplex_of_set X A).obj (Opposite.op (SimplexCategory.mk n)))) := by
    apply Subtype.ext
    simp only [supported_chain_complex, ChainComplex.of_d]
    change ModuleCat.Hom.hom
        (CategoryStruct.comp
          (chain_complex_x_iso_finsupp (TopCat.toSSet.obj X) (n + 1)).inv
          (CategoryStruct.comp
            (((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).d (n + 1) n)
            (chain_complex_x_iso_finsupp (TopCat.toSSet.obj X) n).hom))
        (Finsupp.single (↑σ) 1) = _
    rw [transported_differential_eq_lmapdomain_sum]
    simp only [LinearMap.sum_apply, LinearMap.smul_apply, Finsupp.lmapDomain_apply,
      Finsupp.mapDomain_single, AddSubmonoidClass.coe_finsetSum, Submodule.coe_smul_of_tower, hτ]
  rw [hsum, map_sum]
  refine Finset.sum_congr rfl (fun i _ => ?_)
  rw [map_zsmul, subspace_supported_finsupp_equiv_single X A n (τ i)
    (Finsupp.single_mem_supported R 1 (τ i).2), subspace_supported_simplex_bijection_face]

/-- The degreewise comparison isomorphisms `subspace_supported_x_iso` intertwine the
differential of the supported subcomplex of `singular_subcomplex_of_set X A` with the
differential of the singular chain complex of the subspace `A`, i.e. they assemble
into a chain map. -/
theorem subspace_supported_d_comm :
    ∀ (i j : ℕ), (ComplexShape.down ℕ).Rel i j →
      (supported_chain_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A)).d i j ≫
          (subspace_supported_x_iso (R := R) X A j).hom =
        (subspace_supported_x_iso (R := R) X A i).hom ≫
          ((TopCat.toSSet.obj (TopCat.of A)).chainComplex (ModuleCat.of R R)).d i j := by
  intro i j hij
  obtain rfl : i = j + 1 := hij.symm
  set SumD :
      (((TopCat.toSSet.obj (TopCat.of A)).obj
          (Opposite.op (SimplexCategory.mk (j + 1))) →₀ R)
        →ₗ[R] ((TopCat.toSSet.obj (TopCat.of A)).obj (Opposite.op (SimplexCategory.mk j)) →₀ R)) :=
    ∑ i : Fin (j + 2), (-1 : ℤ) ^ (i : ℕ) •
      Finsupp.lmapDomain R R ((TopCat.toSSet.obj (TopCat.of A)).δ i) with hSumD
  have hphi :
      (chain_complex_x_iso_finsupp (TopCat.toSSet.obj (TopCat.of A)) (j + 1)).inv ≫
        ((TopCat.toSSet.obj (TopCat.of A)).chainComplex (ModuleCat.of R R)).d (j + 1) j ≫
          (chain_complex_x_iso_finsupp (TopCat.toSSet.obj (TopCat.of A)) j).hom =
        ModuleCat.ofHom SumD := by
    apply ModuleCat.hom_ext
    exact transported_differential_eq_lmapdomain_sum (R := R) (TopCat.toSSet.obj (TopCat.of A)) j
  have hcancel :
      ModuleCat.ofHom SumD ≫ (chain_complex_x_iso_finsupp (TopCat.toSSet.obj (TopCat.of A)) j).inv =
        (chain_complex_x_iso_finsupp (TopCat.toSSet.obj (TopCat.of A)) (j + 1)).inv ≫
          ((TopCat.toSSet.obj (TopCat.of A)).chainComplex (ModuleCat.of R R)).d (j + 1) j := by
    rw [← hphi]
    simp [Category.assoc]
  have key :
      (supported_chain_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A)).d (j + 1) j ≫
        (subspace_supported_finsupp_equiv (R := R) X A j).toModuleIso.hom =
      (subspace_supported_finsupp_equiv (R := R) X A (j + 1)).toModuleIso.hom ≫
        ModuleCat.ofHom SumD := by
    apply ModuleCat.hom_ext
    apply (LinearMap.cancel_right (Finsupp.supportedEquivFinsupp (R := R)
      ((singular_subcomplex_of_set X A).obj
        (Opposite.op (SimplexCategory.mk (j + 1))))).symm.surjective).mp
    apply Finsupp.lhom_ext'
    intro σ
    apply LinearMap.ext_ring
    simp only [LinearMap.comp_apply, Finsupp.lsingle_apply]
    have hz : (Finsupp.supportedEquivFinsupp
          ((singular_subcomplex_of_set X A).obj (Opposite.op (SimplexCategory.mk (j + 1))))).symm
          (Finsupp.single σ 1)
        = (⟨Finsupp.single (↑σ) 1, Finsupp.single_mem_supported R 1 σ.2⟩ :
            Finsupp.supported R R
              ((singular_subcomplex_of_set X A).obj
                (Opposite.op (SimplexCategory.mk (j + 1))))) :=
      Subtype.ext (Finsupp.supportedEquivFinsupp_symm_single _ σ 1)
    change ModuleCat.Hom.hom
        ((supported_chain_complex (R := R) (TopCat.toSSet.obj X)
            (singular_subcomplex_of_set X A)).d (j + 1) j ≫
          (subspace_supported_finsupp_equiv (R := R) X A j).toModuleIso.hom)
        ((Finsupp.supportedEquivFinsupp
            ((singular_subcomplex_of_set X A).obj (Opposite.op (SimplexCategory.mk (j + 1))))).symm
          (Finsupp.single σ 1))
      = ModuleCat.Hom.hom
          ((subspace_supported_finsupp_equiv (R := R) X A (j + 1)).toModuleIso.hom ≫
            ModuleCat.ofHom SumD)
          ((Finsupp.supportedEquivFinsupp
              ((singular_subcomplex_of_set X A).obj
                (Opposite.op (SimplexCategory.mk (j + 1))))).symm
            (Finsupp.single σ 1))
    rw [hz]
    change subspace_supported_finsupp_equiv (R := R) X A j
        (ModuleCat.Hom.hom
          ((supported_chain_complex (R := R) (TopCat.toSSet.obj X)
              (singular_subcomplex_of_set X A)).d (j + 1) j)
          ⟨Finsupp.single (↑σ) 1, Finsupp.single_mem_supported R 1 σ.2⟩)
      = SumD (subspace_supported_finsupp_equiv (R := R) X A (j + 1)
          ⟨Finsupp.single (↑σ) 1, Finsupp.single_mem_supported R 1 σ.2⟩)
    rw [subspace_supported_d_single (R := R) X A j σ (Finsupp.single_mem_supported R 1 σ.2),
      subspace_supported_finsupp_equiv_single X A (j + 1) σ (Finsupp.single_mem_supported R 1 σ.2)]
    rw [LinearMap.sum_apply]
    simp only [LinearMap.smul_apply, Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
  rw [subspace_supported_x_iso_hom_eq, subspace_supported_x_iso_hom_eq]
  calc (supported_chain_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A)).d (j + 1) j ≫
        ((subspace_supported_finsupp_equiv (R := R) X A j).toModuleIso.hom ≫
          (chain_complex_x_iso_finsupp (TopCat.toSSet.obj (TopCat.of A)) j).inv)
      = ((supported_chain_complex (R := R) (TopCat.toSSet.obj X)
            (singular_subcomplex_of_set X A)).d (j + 1) j ≫
          (subspace_supported_finsupp_equiv (R := R) X A j).toModuleIso.hom) ≫
          (chain_complex_x_iso_finsupp (TopCat.toSSet.obj (TopCat.of A)) j).inv :=
        (Category.assoc _ _ _).symm
    _ = ((subspace_supported_finsupp_equiv (R := R) X A (j + 1)).toModuleIso.hom ≫
          ModuleCat.ofHom SumD) ≫
          (chain_complex_x_iso_finsupp (TopCat.toSSet.obj (TopCat.of A)) j).inv :=
        congrArg (· ≫ (chain_complex_x_iso_finsupp (TopCat.toSSet.obj (TopCat.of A)) j).inv) key
    _ = (subspace_supported_finsupp_equiv (R := R) X A (j + 1)).toModuleIso.hom ≫
          (ModuleCat.ofHom SumD ≫
            (chain_complex_x_iso_finsupp (TopCat.toSSet.obj (TopCat.of A)) j).inv) :=
        Category.assoc _ _ _
    _ = (subspace_supported_finsupp_equiv (R := R) X A (j + 1)).toModuleIso.hom ≫
          ((chain_complex_x_iso_finsupp (TopCat.toSSet.obj (TopCat.of A)) (j + 1)).inv ≫
            ((TopCat.toSSet.obj (TopCat.of A)).chainComplex (ModuleCat.of R R)).d (j + 1) j) := by
        rw [hcancel]
    _ = ((subspace_supported_finsupp_equiv (R := R) X A (j + 1)).toModuleIso.hom ≫
          (chain_complex_x_iso_finsupp (TopCat.toSSet.obj (TopCat.of A)) (j + 1)).inv) ≫
          ((TopCat.toSSet.obj (TopCat.of A)).chainComplex (ModuleCat.of R R)).d (j + 1) j :=
        (Category.assoc _ _ _).symm

/-- **Supported subcomplex ≅ subspace singular chain complex**: the degreewise
isomorphisms `subspace_supported_x_iso` assemble, via `subspace_supported_d_comm`, into
an isomorphism between the supported subcomplex of `singular_subcomplex_of_set X A` and
the singular chain complex of the subspace `A`. -/
noncomputable def subspace_supported_chain_complex_iso :=
  HomologicalComplex.Hom.isoOfComponents
    (fun n => subspace_supported_x_iso (R := R) X A n)
    (fun i j hij => (subspace_supported_d_comm (R := R) X A i j hij).symm)

end Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexDifferential
