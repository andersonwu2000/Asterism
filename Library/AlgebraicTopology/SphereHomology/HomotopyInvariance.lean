import Mathlib.Algebra.Category.ModuleCat.Abelian
import Mathlib.Algebra.Category.ModuleCat.Colimits
import Mathlib.Algebra.Lie.OfAssociative
import Mathlib.AlgebraicTopology.SingularHomology.HomotopyInvariance
import Mathlib.Combinatorics.Quiver.ReflQuiver
import Mathlib.Topology.EMetricSpace.Paracompact
import Mathlib.Topology.Homotopy.Contractible
import Mathlib.Topology.Separation.Lemmas

/-!
# Homotopy invariance of singular homology

This file packages the homotopy invariance of the singular homology functor
`AlgebraicTopology.singularHomologyFunctor` (with `R`-module coefficients) for the sphere-homology
development: a homotopy equivalence of spaces induces an isomorphism on every singular homology
group, and consequently the singular homology of a contractible space vanishes in each positive
degree.

## Main definitions

* `singular_homology_iso_chain_homology`: the packaged singular homology functor agrees
  definitionally with the chain-level homology of `X`'s singular simplicial set, pinning a single
  citable iso in place of unfolding `singularHomologyFunctor` by hand.
* `homotopy_equiv_induces_singular_iso`, `homotopy_equiv_singular_homology_iso`: a homotopy
  equivalence `X ≃ₕ Y` induces an isomorphism on the `k`-th singular homology functor.

## Main statements

* `homology_map_eq_of_homotopic`: **homotopy invariance of singular homology** — homotopic maps
  induce the same map on singular homology.
* `homology_hom_inv_id`, `homology_inv_hom_id`: the two triangle identities witnessing that the
  map induced by a homotopy equivalence is an isomorphism.
* `contractible_singular_homology_is_zero`: the singular homology of a contractible space vanishes
  in every positive degree.

## Implementation notes

Throughout, `R` is a ring and singular homology is taken with `R`-module coefficients: the `k`-th
singular homology of `X` is
`((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj (ModuleCat.of R R)).obj X`.
-/

open CategoryTheory

namespace Library.AlgebraicTopology.SphereHomology.HomotopyInvariance

variable {R : Type} [Ring R]

/-- The packaged singular homology functor agrees, for every space `X`, definitionally with the
chain-level homology `((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).homology k` of `X`'s
singular simplicial set. Downstream sphere-homology files cite this single iso instead of
unfolding `singularHomologyFunctor` / `whiskeringLeft` / `whiskeringRight` by hand. -/
noncomputable def singular_homology_iso_chain_homology (X : TopCat.{0}) (k : ℕ) :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj X ≅
      ((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).homology k :=
  Iso.refl _

/-- For a homotopy equivalence `h : X ≃ₕ Y`, the induced map on the `k`-th singular homology
followed by the map induced by `h`'s homotopy inverse is the identity on `H_k(X)`. -/
theorem homology_hom_inv_id {X Y : TopCat.{0}}
    (h : ContinuousMap.HomotopyEquiv X Y) (k : ℕ) :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).map (TopCat.ofHom h.toFun) ≫
      ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).map (TopCat.ofHom h.invFun) =
    𝟙 (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj X) := by
  obtain ⟨H₀⟩ := h.left_inv
  rw [← Functor.map_comp]
  have H : TopCat.Homotopy (TopCat.ofHom h.toFun ≫ TopCat.ofHom h.invFun) (𝟙 X) := H₀
  have hcongr := TopCat.Homotopy.congr_homologyMap_singularChainComplexFunctor H
    (ModuleCat.of R R) k
  have hmap : ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).map (TopCat.ofHom h.toFun ≫ TopCat.ofHom h.invFun) =
      ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).map (𝟙 X) := hcongr
  rw [hmap]
  exact CategoryTheory.Functor.map_id _ _

/-- A homotopy equivalence `e : X ≃ₕ Y` induces an isomorphism on the `k`-th singular homology
functor: the forward and inverse maps are `F.map` of `e.toFun` / `e.invFun`, and both round-trip
identities follow from functoriality together with the homotopy invariance of singular homology,
applied to the homotopies extracted from `e.left_inv` / `e.right_inv`. -/
noncomputable def homotopy_equiv_induces_singular_iso {X Y : TopCat.{0}}
    (e : ContinuousMap.HomotopyEquiv X Y) (k : ℕ) :
    (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj X) ≅
    (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj Y) := by
  set F := (AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
      (ModuleCat.of R R)
  refine ⟨F.map (TopCat.ofHom e.toFun), F.map (TopCat.ofHom e.invFun), ?_, ?_⟩
  · rw [← F.map_comp, ← F.map_id]
    obtain ⟨H⟩ := e.left_inv
    exact TopCat.Homotopy.congr_homologyMap_singularChainComplexFunctor H
      (ModuleCat.of R R) k
  · rw [← F.map_comp, ← F.map_id]
    obtain ⟨H⟩ := e.right_inv
    exact TopCat.Homotopy.congr_homologyMap_singularChainComplexFunctor H
      (ModuleCat.of R R) k

/-- The singular homology of a contractible space vanishes in every positive degree: a
contractible space is homotopy equivalent to a point, singular homology is homotopy-invariant, so
`H_k(X) ≅ H_k(Unit)`, and `H_k` of the (totally disconnected) point vanishes for `k ≠ 0`. -/
theorem contractible_singular_homology_is_zero {X : TopCat.{0}}
    [ContractibleSpace X] (k : ℕ) (hk : k ≠ 0) :
    CategoryTheory.Limits.IsZero
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj X) := by
  obtain ⟨e⟩ := ContractibleSpace.hequiv_unit X
  have h_iso : (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj X) ≅
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj (TopCat.of Unit)) :=
    homotopy_equiv_induces_singular_iso e k
  have h_zero : CategoryTheory.Limits.IsZero
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj (TopCat.of Unit)) :=
    AlgebraicTopology.isZero_singularHomologyFunctor_of_totallyDisconnectedSpace
      (ModuleCat.{0} R) k (ModuleCat.of R R) (TopCat.of Unit) hk
  exact h_zero.of_iso h_iso

/-- **Homotopy invariance of singular homology**: if `f` and `g` are homotopic continuous maps
`X → Y`, they induce the same map on the `k`-th singular homology functor. -/
theorem homology_map_eq_of_homotopic {X Y : TopCat.{0}}
    (k : ℕ) {f g : C(X, Y)} (H : f.Homotopic g) :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).map (TopCat.ofHom f) =
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).map (TopCat.ofHom g) := by
  obtain ⟨H₀⟩ := H
  have H' : TopCat.Homotopy (TopCat.ofHom f) (TopCat.ofHom g) := H₀
  exact TopCat.Homotopy.congr_homologyMap_singularChainComplexFunctor H' (ModuleCat.of R R) k

/-- For a homotopy equivalence `h : X ≃ₕ Y`, the map induced on singular homology by `h`'s
homotopy inverse followed by the map induced by `h` is the identity on `H_k(Y)`. -/
theorem homology_inv_hom_id {X Y : TopCat.{0}}
    (h : ContinuousMap.HomotopyEquiv X Y) (k : ℕ) :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).map (TopCat.ofHom h.invFun) ≫
      ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).map (TopCat.ofHom h.toFun) =
    𝟙 (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj Y) := by
  have key := homology_map_eq_of_homotopic (R := R) (X := Y) (Y := Y) k h.right_inv
  rw [← CategoryTheory.Functor.map_comp, ← TopCat.ofHom_comp, key, TopCat.ofHom_id,
    CategoryTheory.Functor.map_id]

/-- A homotopy equivalence `h : X ≃ₕ Y` induces an isomorphism on singular homology, built from
the two functor maps `F.map (ofHom h.toFun)` and `F.map (ofHom h.invFun)`; `homology_hom_inv_id`
and `homology_inv_hom_id` supply the two round-trip identities that make them mutually inverse. -/
noncomputable def homotopy_equiv_singular_homology_iso
    {X Y : TopCat.{0}} (h : ContinuousMap.HomotopyEquiv X Y) (k : ℕ) :
    (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj X) ≅
    (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj Y) := by
  let F := (AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj (ModuleCat.of R R)
  let f : X ⟶ Y := TopCat.ofHom h.toFun
  let g : Y ⟶ X := TopCat.ofHom h.invFun
  have h_hom_inv : F.map f ≫ F.map g = 𝟙 (F.obj X) := homology_hom_inv_id h k
  have h_inv_hom : F.map g ≫ F.map f = 𝟙 (F.obj Y) := homology_inv_hom_id h k
  exact ⟨F.map f, F.map g, h_hom_inv, h_inv_hom⟩

end Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
