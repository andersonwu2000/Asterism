import Library.AlgebraicTopology.SphereHomology.SingularH0Naturality
import Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
import Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology

/-!
# Coproduct and totally disconnected models of `S⁰`'s degree-`0` homology

This file relates two descriptions of the degree-`0` singular homology of the (totally
disconnected) zero-sphere `S⁰`: the coproduct-over-points model coming from
`TotallyDisconnectedSpace`, and the `∐ S⁰ ≅ R × R` identification `sphere_zero_coprod_prod_iso`.
The two models are shown to induce the same codiagonal map, which lets the augmentation
`singularHomology₀ε` be identified with the fold map `LinearMap.fst + LinearMap.snd` composed
with the isomorphism `sphere_zero_h0_iso`.

## Main statements

* `td_iso_sigma_desc_eq_aug`: the totally disconnected homology isomorphism at degree `0`,
  composed with the codiagonal, equals the augmentation map.
* `coprod_prod_desc_eq`: the `∐ S⁰ ≅ R × R` isomorphism, composed with the fold map, is the
  same codiagonal.
* `sphere_zero_augmentation_eq`: the augmentation map for `S⁰` equals `sphere_zero_h0_iso.hom`
  composed with the fold map.

## Implementation notes

The totally disconnected route computes homology as a coproduct indexed by the points of `S⁰`;
`coprod_prod_desc_eq` and `sphere_zero_td_homology_iso_codiag_eq` transport that computation
along `sphere_zero_coprod_prod_iso` to the `R × R` model used elsewhere in the library.
-/

open CategoryTheory CategoryTheory.Limits Simplicial
open Library.AlgebraicTopology.SphereHomology.SingularH0Naturality
open Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
open Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology

namespace Library.AlgebraicTopology.SphereHomology.CoprodDescAndTDBasics

variable {R : Type} [Ring R]

/-- The isomorphism `∐ S⁰ ≅ R × R` (`sphere_zero_coprod_prod_iso`), composed with the fold map
`LinearMap.fst + LinearMap.snd`, agrees with the codiagonal `Sigma.desc (fun _ => 𝟙 R)`.
The proof reduces via `Sigma.hom_ext` to each injection; `ModuleCat.ι_coprodIsoDirectSum_hom`
turns `Sigma.ι ≫ (coprod iso)` into `DirectSum.lof`, and the `finTwoArrow`/`lequivCongrLeft`
identification evaluates to `1` at each point `b`, since exactly one of the two `Fin 2` index
slots hits `b`, giving `1 + 0 = 1`, the identity leg. -/
theorem coprod_prod_desc_eq :
    (sphere_zero_coprod_prod_iso (R := R)).hom ≫
          ModuleCat.ofHom (LinearMap.fst R R R + LinearMap.snd R R R)
      = CategoryTheory.Limits.Sigma.desc (fun _ => 𝟙 (ModuleCat.of R R))  := by
  classical
  apply CategoryTheory.Limits.Sigma.hom_ext
  intro b
  rw [CategoryTheory.Limits.Sigma.ι_desc, ← Category.assoc]
  unfold sphere_zero_coprod_prod_iso
  simp only [Iso.trans_hom, Category.assoc]
  rw [← Category.assoc, ModuleCat.ι_coprodIsoDirectSum_hom]
  apply ModuleCat.hom_ext
  ext
  simp only [ModuleCat.hom_comp, ModuleCat.hom_ofHom, ModuleCat.hom_id, LinearMap.comp_apply,
    LinearEquiv.toModuleIso_hom, LinearMap.id_apply, LinearMap.add_apply, LinearMap.fst_apply,
    LinearMap.snd_apply]
  simp only [LinearEquiv.coe_coe, LinearEquiv.trans_apply, LinearEquiv.finTwoArrow_apply,
    Fin.isValue, DirectSum.linearEquivFunOnFintype_apply, DirectSum.lequivCongrLeft_apply]
  simp only [DirectSum.lof_eq_of]
  by_cases h : sphere_zero_index_equiv.symm 0 = b
  · have hne : sphere_zero_index_equiv.symm 1 ≠ b := by
      rw [← h]
      exact fun he => absurd (sphere_zero_index_equiv.symm.injective he) (by decide)
    rw [h, DirectSum.of_eq_same, DirectSum.of_eq_of_ne _ _ _ hne, add_zero]
  · have hb0 : sphere_zero_index_equiv b ≠ 0 := by
      intro hb0
      exact h (by rw [← hb0, Equiv.symm_apply_apply])
    have hb1 : sphere_zero_index_equiv b = 1 := by omega
    have h1 : sphere_zero_index_equiv.symm 1 = b := by
      rw [← hb1, Equiv.symm_apply_apply]
    rw [DirectSum.of_eq_of_ne _ _ _ h, zero_add, h1, DirectSum.of_eq_same]

section
variable (X : TopCat.{0}) [TotallyDisconnectedSpace X]

/-- The degree-`0` component of the singular chain complex isomorphism for a totally
disconnected space `X` (`singularChainComplexFunctorIsoOfTotallyDisconnectedSpace`) is the
reindexing coproduct map `Sigma.desc (Sigma.ι ∘ toSSetObj₀Equiv)`. -/
theorem td_chain_iso_hom_f_zero :
    (AlgebraicTopology.singularChainComplexFunctorIsoOfTotallyDisconnectedSpace
        (ModuleCat.{0} R) (ModuleCat.of R R) X).hom.f 0
      = Sigma.desc (fun (x0 : (TopCat.toSSet.obj X) _⦋0⦌) =>
          Sigma.ι (fun _ : X => ModuleCat.of R R) (TopCat.toSSetObj₀Equiv x0))  := by
  -- Unfold the td chain iso: its degree-0 leg is `Sigma.map'` along the reindexing map
  -- `toSSetIsoConst.hom.app ⦋0⦌` (the `alternatingFaceMapComplexConst` leg is `𝟙`).
  dsimp [AlgebraicTopology.singularChainComplexFunctorIsoOfTotallyDisconnectedSpace,
    AlgebraicTopology.alternatingFaceMapComplexConst]
  simp only [Category.comp_id]
  -- Reduce to the reindexing map agreeing with `toSSetObj₀Equiv` on each 0-simplex.
  apply Limits.Sigma.hom_ext
  intro x0
  simp only [Limits.Sigma.ι_comp_map', Category.id_comp, Limits.Sigma.ι_desc]
  congr 1
  -- `toSSetIsoConst` at degree 0 evaluates a 0-simplex at `Classical.arbitrary`, while
  -- `toSSetObj₀Equiv` evaluates at `default`; both agree since the 0-simplex is subsingleton.
  simp only [TopCat.toSSetIsoConst, NatIso.ofComponents_inv_app, Iso.symm_hom,
    TopCat.toSSetObj₀Equiv_apply, Functor.const_obj_obj, Nat.reduceAdd,
    Equiv.toIso_inv_hom_apply, Equiv.symm_trans_apply, Equiv.symm_symm,
    TotallyDisconnectedSpace.continuousMapEquivOfConnectedSpace, Equiv.coe_fn_mk]
  exact congrArg _ (Subsingleton.elim _ _)

/-- Under the totally disconnected homology isomorphism at degree `0`
(`singularHomologyFunctorZeroOfTotallyDisconnectedSpace`), the homology class of `liftCycles g`
is computed by post-composing `g` with the degree-`0` chain isomorphism
`singularChainComplexFunctorIsoOfTotallyDisconnectedSpace`. -/
theorem td_liftcycles_homology_eq_chain_image
    (g : ModuleCat.of R R ⟶ ((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).X 0) :
      (((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).liftCycles g 0 (by simp) (by simp))
        ≫ ((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).homologyπ 0
        ≫ (AlgebraicTopology.singularHomologyFunctorZeroOfTotallyDisconnectedSpace
              (ModuleCat.{0} R) (ModuleCat.of R R) X).hom
        = g ≫ (AlgebraicTopology.singularChainComplexFunctorIsoOfTotallyDisconnectedSpace
              (ModuleCat.{0} R) (ModuleCat.of R R) X).hom.f 0  := by
  simp only [AlgebraicTopology.singularHomologyFunctorZeroOfTotallyDisconnectedSpace,
    Iso.trans_hom, Functor.mapIso_hom, HomologicalComplex.homologyFunctor_map]
  erw [HomologicalComplex.homologyπ_naturality_assoc,
    HomologicalComplex.liftCycles_comp_cyclesMap_assoc]
  simp only [ChainComplex.alternatingConstHomologyZero, HomologicalComplex.homologyπ,
    HomologicalComplex.liftCycles]
  erw [ShortComplex.LeftHomologyData.homologyπ_comp_homologyIso_hom]
  erw [ShortComplex.LeftHomologyData.liftCycles_comp_cyclesIso_hom_assoc]
  simp only [ChainComplex.alternatingConstHomologyDataZero,
    ShortComplex.HomologyData.ofZeros_left, ShortComplex.LeftHomologyData.ofZeros_π,
    ShortComplex.LeftHomologyData.liftK]
  rfl

/-- For a `0`-simplex `x` of a totally disconnected space `X`, the homology class of the chain
`ιChainComplex x`, viewed through the totally disconnected homology isomorphism, is the
coproduct injection `Sigma.ι` at the point `i := toSSetObj₀Equiv x` named by `x`. The proof
composes two independent facts: `td_liftcycles_homology_eq_chain_image` (generic in the
`0`-chain `g`) identifies the class with the chain image `g ≫ chainIso.hom.f 0`, and
`td_chain_iso_hom_f_zero` identifies that chain iso with the reindexing coproduct map; at
`g := ιChainComplex x = Sigma.ι x`, `Sigma.ι_desc` collapses the reindexing to
`Sigma.ι (toSSetObj₀Equiv x)`. -/
theorem td_gen_maps_to_sigma_inj (x : (TopCat.toSSet.obj X) _⦋0⦌) :
    ∃ i : X,
      (((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).liftCycles
          ((TopCat.toSSet.obj X).ιChainComplex x) 0 (by simp) (by simp))
        ≫ ((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).homologyπ 0
        ≫ (AlgebraicTopology.singularHomologyFunctorZeroOfTotallyDisconnectedSpace
              (ModuleCat.{0} R) (ModuleCat.of R R) X).hom
        = Sigma.ι (fun _ : X => ModuleCat.of R R) i  := by
  refine ⟨TopCat.toSSetObj₀Equiv x, ?_⟩
  refine (td_liftcycles_homology_eq_chain_image X ((TopCat.toSSet.obj X).ιChainComplex x)).trans ?_
  rw [td_chain_iso_hom_f_zero]
  simp only [SSet.ιChainComplex]
  exact Sigma.ι_desc _ _

/-- Composing the totally disconnected homology isomorphism with the codiagonal
`Sigma.desc (fun _ => 𝟙 R)` sends the homology class of `liftCycles (ιChainComplex x)` to the
identity, for every `0`-simplex `x`. -/
theorem td_gen_codiag (x : (TopCat.toSSet.obj X) _⦋0⦌) :
    (((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).liftCycles
        ((TopCat.toSSet.obj X).ιChainComplex x) 0 (by simp) (by simp))
      ≫ ((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).homologyπ 0
      ≫ ((AlgebraicTopology.singularHomologyFunctorZeroOfTotallyDisconnectedSpace
            (ModuleCat.{0} R) (ModuleCat.of R R) X).hom
          ≫ CategoryTheory.Limits.Sigma.desc (fun _ => 𝟙 (ModuleCat.of R R)))
    = 𝟙 (ModuleCat.of R R)  := by
  obtain ⟨i, hi⟩ := td_gen_maps_to_sigma_inj (R := R) X x
  rw [reassoc_of% hi, Limits.Sigma.ι_desc]

/-- Composing the totally disconnected homology isomorphism at degree `0` with the codiagonal
`Sigma.desc (fun _ => 𝟙 R)` equals the augmentation map `singularHomology₀ε`. The proof checks
equality against `singularHomology₀ε` on generators via `homology_zero_hom_ext`, reducing to
`td_gen_codiag`. -/
theorem td_iso_sigma_desc_eq_aug :
    (AlgebraicTopology.singularHomologyFunctorZeroOfTotallyDisconnectedSpace
        (ModuleCat.{0} R) (ModuleCat.of R R) X).hom ≫
      CategoryTheory.Limits.Sigma.desc (fun _ => 𝟙 (ModuleCat.of R R)) =
      X.singularHomology₀ε (ModuleCat.of R R)  := by
  refine homology_zero_hom_ext (ModuleCat.of R R) ?_
  intro x
  have hgen : (((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).liftCycles
        ((TopCat.toSSet.obj X).ιChainComplex x) 0 (by simp) (by simp))
      ≫ ((TopCat.toSSet.obj X).chainComplex (ModuleCat.of R R)).homologyπ 0
      ≫ X.singularHomology₀ε (ModuleCat.of R R) = 𝟙 (ModuleCat.of R R) := by
    dsimp only [TopCat.singularHomology₀ε]
    rw [SSet.liftCycles_ιChainComplex_homologyπ_homology₀ε]
  rw [hgen]
  exact td_gen_codiag X x

end

/-- For the totally disconnected sphere `S⁰`, composing the singular homology isomorphism
`singularHomology₀Iso` at degree `0` with the codiagonal `Sigma.desc (fun _ => 𝟙 R)` equals the
analogous composite through the totally disconnected homology isomorphism
`singularHomologyFunctorZeroOfTotallyDisconnectedSpace`. The proof strips `ε` from the
`π₀`-indexed side via `singularHomology₀Iso_sigma_desc_id`, then closes with the analogous
totally disconnected identity `td_iso_sigma_desc_eq_aug`, reversed. -/
theorem sphere_zero_td_homology_iso_codiag_eq
    [TotallyDisconnectedSpace (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))] :
    (((TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1)).singularHomology₀Iso
            (ModuleCat.of R R)).hom ≫
        CategoryTheory.Limits.Sigma.desc (fun _ => 𝟙 (ModuleCat.of R R))) =
      (AlgebraicTopology.singularHomologyFunctorZeroOfTotallyDisconnectedSpace
            (ModuleCat.{0} R) (ModuleCat.of R R)
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))).hom ≫
        CategoryTheory.Limits.Sigma.desc (fun _ => 𝟙 (ModuleCat.of R R)) := by
  have h_td := td_iso_sigma_desc_eq_aug (R := R)
    (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))
  rw [TopCat.singularHomology₀Iso_sigma_desc_id]
  exact h_td.symm

/-- The augmentation map `singularHomology₀ε` for the totally disconnected sphere `S⁰` equals
the composite of the totally disconnected homology isomorphism at degree `0` with the codiagonal
`Sigma.desc (fun _ => 𝟙 R)`; the reverse direction of `td_iso_sigma_desc_eq_aug`. -/
theorem aug_eq_coprod_desc
    [TotallyDisconnectedSpace (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))] :
    TopCat.singularHomology₀ε
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))
        (ModuleCat.of R R)
      = (AlgebraicTopology.singularHomologyFunctorZeroOfTotallyDisconnectedSpace
            (ModuleCat.{0} R) (ModuleCat.of R R)
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))).hom ≫
          CategoryTheory.Limits.Sigma.desc (fun _ => 𝟙 (ModuleCat.of R R)) :=
    (td_iso_sigma_desc_eq_aug
      (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))).symm

/-- The augmentation map `singularHomology₀ε` for the totally disconnected sphere `S⁰` equals
the singular homology isomorphism `sphere_zero_h0_iso` composed with the fold map
`LinearMap.fst + LinearMap.snd`. The proof factors both sides through the totally disconnected
coproduct model: `aug_eq_coprod_desc` identifies `ε` with the coproduct-isomorphism composite,
and `coprod_prod_desc_eq` identifies that same composite, up to the `∐ ≅ R × R` isomorphism,
with the fold map, so the two sides agree by `rfl` after reassociating. -/
theorem sphere_zero_augmentation_eq :
    TopCat.singularHomology₀ε
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))
        (ModuleCat.of R R)
      = (sphere_zero_h0_iso (R := R)).hom ≫
          ModuleCat.ofHom (LinearMap.fst R R R + LinearMap.snd R R R)  := by
  haveI : Finite ↥(Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1) := sphere_zero_finite
  haveI : TotallyDisconnectedSpace
      (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1)) := inferInstance
  have hA : TopCat.singularHomology₀ε
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))
        (ModuleCat.of R R)
      = (AlgebraicTopology.singularHomologyFunctorZeroOfTotallyDisconnectedSpace
            (ModuleCat.{0} R) (ModuleCat.of R R)
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))).hom ≫
          CategoryTheory.Limits.Sigma.desc (fun _ => 𝟙 (ModuleCat.of R R)) := aug_eq_coprod_desc
  have hB : (sphere_zero_coprod_prod_iso (R := R)).hom ≫
          ModuleCat.ofHom (LinearMap.fst R R R + LinearMap.snd R R R)
      = CategoryTheory.Limits.Sigma.desc (fun _ => 𝟙 (ModuleCat.of R R)) := coprod_prod_desc_eq
  rw [hA, ← hB, ← Category.assoc]
  rfl

end Library.AlgebraicTopology.SphereHomology.CoprodDescAndTDBasics
