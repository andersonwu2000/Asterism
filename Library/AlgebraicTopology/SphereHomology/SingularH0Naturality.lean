import Mathlib.Algebra.Category.ModuleCat.Abelian
import Mathlib.Algebra.Category.ModuleCat.Colimits
import Mathlib.Algebra.Lie.OfAssociative
import Mathlib.AlgebraicTopology.SingularHomology.HomologyZero
import Mathlib.CategoryTheory.EffectiveEpi.Comp
import Mathlib.CategoryTheory.ExtremalEpi
import Mathlib.Combinatorics.Quiver.ReflQuiver

/-!
# Naturality of the degree-zero singular homology augmentation

This file establishes naturality of the canonical isomorphism `homology₀Iso` between the
degree-zero homology of a simplicial set (or, via `toSSet`, of a topological space) and the
coproduct of the coefficient module indexed by path components. From this we deduce naturality
of the singular homology augmentation `ε : H₀(X) ⟶ R`, and conclude that the map induced on
`H₀` by a morphism between path-connected spaces is a monomorphism.

## Main statements

* `homology_zero_iso_naturality_sset`: naturality of `homology₀Iso` for simplicial sets.
* `singular_h0_iso_naturality`: naturality of `homology₀Iso` for topological spaces.
* `singular_h0_augmentation_naturality`: naturality of the augmentation `ε : H₀(·) ⟶ R`.
* `singular_h0_map_mono_of_path_connected`: the induced map on `H₀` between path-connected
  spaces is a monomorphism.
-/

open CategoryTheory CategoryTheory.Limits Simplicial

namespace Library.AlgebraicTopology.SphereHomology.SingularH0Naturality

section
variable {R : Type} [Ring R] {X Y : TopCat.{0}}

/-- Reindexing a coproduct by `Sigma.map'` and then descending along all-identity legs agrees
with descending directly: both sides reduce, after `Sigma.hom_ext`, to the identity-leg
composite via `Sigma.ι_comp_map'` and `Sigma.ι_desc`. -/
theorem sigma_map_id_desc_id (f : X ⟶ Y) :
    CategoryTheory.Limits.Sigma.map' (SSet.π₀Functor.map (TopCat.toSSet.map f))
          (fun _ => 𝟙 (ModuleCat.of R R)) ≫
        (CategoryTheory.Limits.Sigma.desc fun _ => 𝟙 (ModuleCat.of R R))
      = (CategoryTheory.Limits.Sigma.desc fun _ => 𝟙 (ModuleCat.of R R)) := by
  apply Sigma.hom_ext
  intro b
  rw [← Category.assoc, Sigma.ι_comp_map', Category.id_comp, Sigma.ι_desc, Sigma.ι_desc]

end

section
variable {C : Type u} [Category.{v} C] [HasCoproducts.{0} C] [Preadditive C]
  [CategoryWithHomology C]

/-- Maps out of `X.homology R 0` are determined by their values on the degree-zero chain
generators: it suffices to check equality after precomposing with `ιChainComplex x` and
`homologyπ 0`, for every `0`-simplex `x`. -/
theorem homology_zero_hom_ext {X : SSet.{0}} (R : C) {Z : C}
    {f g : X.homology R 0 ⟶ Z}
    (h : ∀ x : X _⦋0⦌,
      (X.chainComplex R).liftCycles (X.ιChainComplex x) 0 (by simp) (by simp)
          ≫ (X.chainComplex R).homologyπ 0 ≫ f
        = (X.chainComplex R).liftCycles (X.ιChainComplex x) 0 (by simp) (by simp)
          ≫ (X.chainComplex R).homologyπ 0 ≫ g) :
    f = g := by
  rw [← cancel_epi (X.homology₀Iso R).inv]
  ext j
  obtain ⟨x, rfl⟩ := SSet.π₀.mk_surjective j
  rw [← SSet.liftCycles_ιChainComplex_homologyπ_homology₀Iso_hom X R x]
  simp only [Category.assoc, Iso.hom_inv_id_assoc]
  exact h x

section
variable {X Y : SSet.{0}}

/-- Generator-level naturality of `homology₀Iso` along the reindexing map on path components
induced by a morphism of simplicial sets `φ`. -/
theorem homology_zero_iso_naturality_gen (φ : X ⟶ Y) (R : C) (x : X _⦋0⦌) :
    (X.chainComplex R).liftCycles (X.ιChainComplex x) 0 (by simp) (by simp)
        ≫ (X.chainComplex R).homologyπ 0
        ≫ (HomologicalComplex.homologyMap (((SSet.chainComplexFunctor C).obj R).map φ) 0
            ≫ (Y.homology₀Iso R).hom)
      = (X.chainComplex R).liftCycles (X.ιChainComplex x) 0 (by simp) (by simp)
        ≫ (X.chainComplex R).homologyπ 0
        ≫ ((X.homology₀Iso R).hom
            ≫ CategoryTheory.Limits.Sigma.map' (SSet.π₀Functor.map φ) (fun _ => 𝟙 R)) := by
  simp only [HomologicalComplex.homologyπ_naturality_assoc,
    HomologicalComplex.liftCycles_comp_cyclesMap_assoc, SSet.ι_chainComplexMap_f,
    SSet.liftCycles_ιChainComplex_homologyπ_homology₀Iso_hom,
    SSet.liftCycles_ιChainComplex_homologyπ_homology₀Iso_hom_assoc,
    Sigma.ι_comp_map', Category.id_comp]
  congr 1

/-- Naturality of the degree-zero homology isomorphism `homology₀Iso` for simplicial sets: the
square induced by `homologyMap` and the coproduct reindexing `Sigma.map'` along `φ`
commutes. -/
theorem homology_zero_iso_naturality_sset (φ : X ⟶ Y) (R : C) :
    HomologicalComplex.homologyMap (((SSet.chainComplexFunctor C).obj R).map φ) 0
        ≫ (Y.homology₀Iso R).hom
      = (X.homology₀Iso R).hom ≫
        CategoryTheory.Limits.Sigma.map' (SSet.π₀Functor.map φ) (fun _ => 𝟙 R) := by
  apply homology_zero_hom_ext
  intro x
  exact homology_zero_iso_naturality_gen φ R x

end

end

section
variable {R : Type} [Ring R] {X Y : TopCat.{0}}

/-- Naturality of the degree-zero singular homology isomorphism `homology₀Iso` for topological
spaces: the singular-homology functor's action on `f` is intertwined with the reindexing of
path components induced by `f`. -/
theorem singular_h0_iso_naturality (f : X ⟶ Y) :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
          (ModuleCat.of R R)).map f ≫ ((TopCat.toSSet.obj Y).homology₀Iso (ModuleCat.of R R)).hom
      = ((TopCat.toSSet.obj X).homology₀Iso (ModuleCat.of R R)).hom ≫
        CategoryTheory.Limits.Sigma.map' (SSet.π₀Functor.map (TopCat.toSSet.map f))
          (fun _ => 𝟙 (ModuleCat.of R R)) := by
  exact homology_zero_iso_naturality_sset (TopCat.toSSet.map f) (ModuleCat.of R R)

/-- Naturality of the degree-zero singular augmentation `ε : H₀(·) ⟶ R`: unfolding
`ε = (homology₀Iso).hom ≫ Sigma.desc (const 𝟙)`, this reduces to naturality of the degree-zero
homology isomorphism (`singular_h0_iso_naturality`) composed with the coproduct fact that
reindexing then descending by all-identity legs is descending directly
(`sigma_map_id_desc_id`). -/
theorem singular_h0_augmentation_naturality (f : X ⟶ Y) :
    (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
          (ModuleCat.of R R)).map f) ≫ TopCat.singularHomology₀ε Y (ModuleCat.of R R)
      = TopCat.singularHomology₀ε X (ModuleCat.of R R) := by
  dsimp only [TopCat.singularHomology₀ε, SSet.homology₀ε]
  erw [← Category.assoc, singular_h0_iso_naturality f, Category.assoc, sigma_map_id_desc_id f]
  rfl

/-- **Injectivity of `H₀` between path-connected spaces**: for a morphism `f : X ⟶ Y` of
path-connected topological spaces, the induced map on degree-zero singular homology
`H₀(f) : H₀(X) ⟶ H₀(Y)` is a monomorphism. This follows from naturality of the augmentation
`ε : H₀(·) ⟶ R` and the fact that `ε_X` is an isomorphism when `X` is path-connected. -/
theorem singular_h0_map_mono_of_path_connected
    (hX : PathConnectedSpace X) (_hY : PathConnectedSpace Y) (f : X ⟶ Y) :
    CategoryTheory.Mono
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
          (ModuleCat.of R R)).map f) := by
  haveI := hX
  have hnat := singular_h0_augmentation_naturality (R := R) f
  exact CategoryTheory.mono_of_mono_fac hnat

end

end Library.AlgebraicTopology.SphereHomology.SingularH0Naturality
