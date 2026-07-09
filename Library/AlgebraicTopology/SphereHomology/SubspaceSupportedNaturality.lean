import Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
import Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexBasic
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexDifferential
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

/-!
# Naturality of the subspace-supported homology bridge

This file shows that the isomorphism `subspace_supported_homology_iso`, identifying the
homology of an `A`-supported singular subcomplex with the singular homology of `A`, is natural
in `A`: for a subspace inclusion `S ⊆ T`, transporting the supported-subcomplex inclusion
`supported_chain_complex_incl` along the bridge isomorphisms on both ends agrees with the map
induced on singular homology by the topological inclusion `S ↪ T`.

The proof builds up to the homology-level square through three intermediate naturality squares,
each transporting the previous one through one more layer of the bridge: a
finitely-supported-function square (`subspace_supported_incl_finsupp_naturality`), a per-degree
chain-module square (`subspace_supported_x_incl_naturality`), and a full chain-complex square
(`subspace_supported_chain_incl_naturality`).

## Main statements

* `subspace_supported_homology_iso_naturality`: the headline result, identifying
  `homologyMap (supported_chain_complex_incl h) ≫ (subspace_supported_homology_iso X T k).hom`
  with `(subspace_supported_homology_iso X S k).hom ≫` the map induced on singular homology by
  the inclusion `S ↪ T`.
* `subspace_supported_chain_incl_naturality`: the chain-complex-level naturality square.
* `subspace_supported_x_incl_naturality`: the per-degree chain-module naturality square.
* `subspace_supported_incl_finsupp_naturality`: the finitely-supported-function naturality
  square underlying the bridge.

## Implementation notes

`transported_subspace_incl_map_eq` and `subspace_supported_incl_finsupp_single` are auxiliary
lemmas: the former conjugates the SSet chain map of the inclusion into a plain
`Finsupp.lmapDomain`, and the latter checks the finsupp-level square on a single generator; both
feed into `subspace_supported_incl_finsupp_naturality`.
-/

open CategoryTheory
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexBasic
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexDifferential
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.SubspaceSupportedNaturality

variable {R : Type} [Ring R] (X : TopCat.{0}) {S T : Set X} (h : S ⊆ T)

/-- The SSet `chainComplexMap` of a subspace inclusion, conjugated by the
`chain_complex_x_iso_finsupp` bridge on each end, agrees with the plain `Finsupp.lmapDomain` map
induced by the inclusion on simplex sets. Auxiliary to
`subspace_supported_incl_finsupp_naturality`. -/
theorem transported_subspace_incl_map_eq (n : ℕ) :
    (chain_complex_x_iso_finsupp (R := R) (TopCat.toSSet.obj (TopCat.of S)) n).inv ≫
        (SSet.chainComplexMap
          (TopCat.toSSet.map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩))
          (ModuleCat.of R R)).f n ≫
        (chain_complex_x_iso_finsupp (R := R) (TopCat.toSSet.obj (TopCat.of T)) n).hom
      = ModuleCat.ofHom (Finsupp.lmapDomain R R
          ((TopCat.toSSet.map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩)).app
            (Opposite.op (SimplexCategory.mk n)))) := by
  rw [Iso.inv_comp_eq]
  apply SSet.chainComplex_hom_ext
  intro σ
  rw [← Category.assoc, SSet.ι_chainComplexMap_f, chain_complex_x_iso_finsupp_single,
    ← Category.assoc, chain_complex_x_iso_finsupp_single, ← ModuleCat.ofHom_comp]
  congr 1
  ext c
  simp [Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]

/-- Single-generator naturality of the supported→Finsupp bridge equiv
`subspace_supported_finsupp_equiv` over an inclusion `S ⊆ T`: reduces both sides to
`subspace_supported_finsupp_equiv_single` on the two ends, then closes the residual bijection
compatibility `bij_T ⟨σ,_⟩ = incl (bij_S σ)` by cancelling `(of T).toSSetObjEquiv` via
injectivity and checking pointwise. Auxiliary to `subspace_supported_incl_finsupp_naturality`. -/
theorem subspace_supported_incl_finsupp_single (n : ℕ)
    (hle : singular_subcomplex_of_set X S ≤ singular_subcomplex_of_set X T)
    (σ : ↥((singular_subcomplex_of_set X S).obj (Opposite.op (SimplexCategory.mk n)))) :
    (ModuleCat.Hom.hom
        ((supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X) hle).f n ≫
          (subspace_supported_finsupp_equiv (R := R) X T n).toModuleIso.hom))
      ⟨Finsupp.single (↑σ) (1 : R), Finsupp.single_mem_supported R 1 σ.2⟩
    = (ModuleCat.Hom.hom
        ((subspace_supported_finsupp_equiv (R := R) X S n).toModuleIso.hom ≫
          ModuleCat.ofHom
            (Finsupp.lmapDomain R R
              ((TopCat.toSSet.map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩)).app
                (Opposite.op (SimplexCategory.mk n))))))
      ⟨Finsupp.single (↑σ) (1 : R), Finsupp.single_mem_supported R 1 σ.2⟩ := by
  have hmemT : (↑σ) ∈ (singular_subcomplex_of_set X T).obj (Opposite.op (SimplexCategory.mk n)) :=
    hle (Opposite.op (SimplexCategory.mk n)) σ.2
  have hL := subspace_supported_finsupp_equiv_single (R := R) X T n ⟨(↑σ), hmemT⟩
    (Finsupp.single_mem_supported R 1 hmemT)
  have hR := subspace_supported_finsupp_equiv_single (R := R) X S n σ
    (Finsupp.single_mem_supported R 1 σ.2)
  simp only [ModuleCat.hom_comp, LinearMap.comp_apply,
    LinearEquiv.toModuleIso_hom, ModuleCat.hom_ofHom]
  change (subspace_supported_finsupp_equiv (R := R) X T n)
      ((ModuleCat.Hom.hom ((supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X) hle).f n))
        ⟨Finsupp.single (↑σ) (1:R), Finsupp.single_mem_supported R 1 σ.2⟩) =
    Finsupp.lmapDomain R R
        ⇑(ConcreteCategory.hom
            ((TopCat.toSSet.map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩)).app
              (Opposite.op (SimplexCategory.mk n))))
      (subspace_supported_finsupp_equiv (R := R) X S n ⟨Finsupp.single (↑σ) (1:R),
        Finsupp.single_mem_supported R 1 σ.2⟩)
  have hbij : subspace_supported_simplex_bijection X T n ⟨(↑σ), hmemT⟩
      = (TopCat.toSSet.map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩)).app
          (Opposite.op (SimplexCategory.mk n)) (subspace_supported_simplex_bijection X S n σ) := by
    apply ((TopCat.of T).toSSetObjEquiv (Opposite.op (SimplexCategory.mk n))).injective
    ext z
    rfl
  rw [show (ModuleCat.Hom.hom
        ((supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X) hle).f n))
        ⟨Finsupp.single (↑σ) (1 : R), Finsupp.single_mem_supported R 1 σ.2⟩
      = (⟨Finsupp.single (↑σ) (1 : R), Finsupp.single_mem_supported R 1 hmemT⟩ :
          ↥(Finsupp.supported R R
            ((singular_subcomplex_of_set X T).obj (Opposite.op (SimplexCategory.mk n)))))
      from rfl, hL, hR, Finsupp.lmapDomain_apply, Finsupp.mapDomain_single, hbij]

/-- Finsupp-level naturality of the supported→Finsupp bridge equiv
`subspace_supported_finsupp_equiv` over an inclusion `S ⊆ T`: transporting the
supported-subcomplex inclusion along the bridge on both ends agrees with the
`Finsupp.lmapDomain` map induced by the inclusion on simplex sets. -/
theorem subspace_supported_incl_finsupp_naturality (n : ℕ)
    (hle : singular_subcomplex_of_set X S ≤ singular_subcomplex_of_set X T) :
    (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X) hle).f n ≫
        (subspace_supported_finsupp_equiv (R := R) X T n).toModuleIso.hom
      = (subspace_supported_finsupp_equiv (R := R) X S n).toModuleIso.hom ≫
        ModuleCat.ofHom (Finsupp.lmapDomain R R
          ((TopCat.toSSet.map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩)).app
          (Opposite.op (SimplexCategory.mk n)))) := by
  apply ModuleCat.hom_ext
  change (_ : ↥(Finsupp.supported R R ((singular_subcomplex_of_set X S).obj
    (Opposite.op (SimplexCategory.mk n)))) →ₗ[R] _) = _
  rw [← LinearMap.cancel_right (Finsupp.supportedEquivFinsupp (R := R) _).symm.surjective]
  apply Finsupp.lhom_ext'
  intro σ
  apply LinearMap.ext_ring
  simp only [LinearMap.comp_apply, Finsupp.lsingle_apply, LinearEquiv.coe_coe]
  rw [show (Finsupp.supportedEquivFinsupp ((singular_subcomplex_of_set X S).obj
        (Opposite.op (SimplexCategory.mk n)))).symm (Finsupp.single σ (1 : R))
        = ⟨Finsupp.single (↑σ) (1 : R), Finsupp.single_mem_supported R 1 σ.2⟩ from
      Subtype.ext (by rw [Finsupp.supportedEquivFinsupp_symm_single])]
  exact subspace_supported_incl_finsupp_single X h n hle σ

/-- Per-degree naturality of the subspace/supported bridge iso `subspace_supported_x_iso` over an
inclusion `S ⊆ T`. Unfolds both `.hom` legs via `subspace_supported_x_iso_hom_eq` into
`finsupp_equiv ≫ chain_complex_x_iso_finsupp.inv`, then cancels the chain-iso factors:
`transported_subspace_incl_map_eq` conjugates the SSet `chainComplexMap` into a `lmapDomain`,
and `subspace_supported_incl_finsupp_naturality` is the residual finsupp-level square. -/
theorem subspace_supported_x_incl_naturality (n : ℕ)
    (hle : singular_subcomplex_of_set X S ≤ singular_subcomplex_of_set X T) :
    (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X) hle).f n ≫
        (subspace_supported_x_iso (R := R) X T n).hom
      = (subspace_supported_x_iso (R := R) X S n).hom ≫
        (SSet.chainComplexMap
          (TopCat.toSSet.map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩))
          (ModuleCat.of R R)).f n := by
  have hA := transported_subspace_incl_map_eq (R := R) X h n
  have hkey := subspace_supported_incl_finsupp_naturality (R := R) X h n hle
  have hcancel :
      (chain_complex_x_iso_finsupp (R := R) (TopCat.toSSet.obj (TopCat.of S)) n).inv ≫
          (SSet.chainComplexMap
            (TopCat.toSSet.map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩))
            (ModuleCat.of R R)).f n
        = ModuleCat.ofHom (Finsupp.lmapDomain R R
            ((TopCat.toSSet.map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩)).app
              (Opposite.op (SimplexCategory.mk n)))) ≫
          (chain_complex_x_iso_finsupp (R := R) (TopCat.toSSet.obj (TopCat.of T)) n).inv := by
    rw [← hA]; simp [Category.assoc]
  rw [subspace_supported_x_iso_hom_eq, subspace_supported_x_iso_hom_eq]
  exact (Category.assoc _ _ _).symm.trans <|
    (hkey =≫ _).trans <|
      (Category.assoc _ _ _).trans <|
        (_ ≫= hcancel.symm).trans (Category.assoc _ _ _).symm

/-- Chain-level naturality of the subspace/supported bridge iso
`subspace_supported_chain_complex_iso` over an inclusion `S ⊆ T`. Reduces the
`HomologicalComplex`-morphism equality to a degreewise square via `HomologicalComplex.hom_ext`,
unfolds `.f n` of both composites and of the `isoOfComponents`-built
`subspace_supported_chain_complex_iso` (its degree-`n` component is `subspace_supported_x_iso`),
leaving the single per-degree naturality brick `subspace_supported_x_incl_naturality`. -/
theorem subspace_supported_chain_incl_naturality
    (hle : singular_subcomplex_of_set X S ≤ singular_subcomplex_of_set X T) :
    supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X) hle
        ≫ (subspace_supported_chain_complex_iso X T).hom
      = (subspace_supported_chain_complex_iso X S).hom
        ≫ SSet.chainComplexMap
            (TopCat.toSSet.map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩))
            (ModuleCat.of R R) := by
  apply HomologicalComplex.hom_ext
  intro n
  simp only [HomologicalComplex.comp_f, subspace_supported_chain_complex_iso,
    HomologicalComplex.Hom.isoOfComponents_hom_f]
  exact subspace_supported_x_incl_naturality (R := R) X h n hle

/-- **Naturality of the subspace-supported homology bridge**: the isomorphism
`subspace_supported_homology_iso`, identifying the homology of an `A`-supported singular
subcomplex with the singular homology of `A`, is natural in `A`. The whole homology-level
square reduces to a single chain-level naturality square
`subspace_supported_chain_incl_naturality` (the supported-subcomplex inclusion, transported
through `subspace_supported_chain_complex_iso` on both ends, equals the singular chain map of
the inclusion), lifted to homology by `homologyMap` functoriality. -/
theorem subspace_supported_homology_iso_naturality (k : ℕ)
    (hle : singular_subcomplex_of_set X S ≤ singular_subcomplex_of_set X T) :
    HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X) hle) k
        ≫ (subspace_supported_homology_iso X T k).hom
      = (subspace_supported_homology_iso X S k).hom
        ≫ ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
              (ModuleCat.of R R)).map
            (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩) := by
  have hsq := subspace_supported_chain_incl_naturality (R := R) X h hle
  have hkey := congrArg (fun φ => HomologicalComplex.homologyMap φ k) hsq
  simp only [HomologicalComplex.homologyMap_comp] at hkey
  have hT : (subspace_supported_homology_iso X T k).hom
      = HomologicalComplex.homologyMap
          (subspace_supported_chain_complex_iso (R := R) X T).hom k := by
    simp only [subspace_supported_homology_iso, Iso.trans_hom, Functor.mapIso_hom,
      HomologicalComplex.homologyFunctor_map, Iso.symm_hom, singular_homology_iso_chain_homology,
      Iso.refl_inv]
    exact Category.comp_id _
  have hS : (subspace_supported_homology_iso X S k).hom
      = HomologicalComplex.homologyMap
          (subspace_supported_chain_complex_iso (R := R) X S).hom k := by
    simp only [subspace_supported_homology_iso, Iso.trans_hom, Functor.mapIso_hom,
      HomologicalComplex.homologyFunctor_map, Iso.symm_hom, singular_homology_iso_chain_homology,
      Iso.refl_inv]
    exact Category.comp_id _
  have hsing : ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩)
      = HomologicalComplex.homologyMap
          (SSet.chainComplexMap
            (TopCat.toSSet.map (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩))
            (ModuleCat.of R R)) k := by
    rfl
  rw [hT, hS, hsing]
  exact hkey

end Library.AlgebraicTopology.SphereHomology.SubspaceSupportedNaturality
