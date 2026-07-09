import Library.AlgebraicTopology.MayerVietoris.ShortExactComplex

/-!
# Supported subcomplexes and the singular chains of a subspace

For a topological space `X` and a subspace `A ⊆ X`, the singular simplices of `X` supported in
`A` (those whose image lies in `A`) are in natural bijection with the singular simplices of `A`
itself. This file promotes that bijection to the degree-`n` term of the singular chain complex:
the submodule of `R`-chains on `X` supported in `A` is linearly equivalent, and in fact
canonically isomorphic as a term of a chain complex, to the free `R`-module on the singular
simplices of `A`. The bijection is also shown to commute with the simplicial face maps, and the
underlying isomorphism is unfolded into its two constituent pieces for later rewriting.

## Main definitions

* `continuous_map_range_subset_equiv`: continuous maps `T → X` with range in `A` correspond to
  continuous maps `T → ↥A`.
* `subspace_supported_simplex_bijection`: the singular `n`-simplices of `X` supported in `A`
  correspond to the singular `n`-simplices of `A`.
* `subspace_supported_finsupp_equiv`: the linear equivalence between `R`-chains on `X` supported
  in `A` and the free `R`-module on the singular `n`-simplices of `A`.
* `subspace_supported_x_iso`: the degree-`n` term of the supported subcomplex is isomorphic, as
  an `R`-module, to the degree-`n` term of the singular chain complex of `A`.

## Main statements

* `subspace_supported_finsupp_equiv_single`: `subspace_supported_finsupp_equiv` sends the
  generator of a supported simplex to the generator of the corresponding `A`-simplex.
* `subspace_supported_simplex_bijection_face`: `subspace_supported_simplex_bijection` commutes
  with the simplicial face maps.
* `subspace_supported_x_iso_hom_eq`: the forward map of `subspace_supported_x_iso` unfolds as a
  composite of the isomorphism induced by `subspace_supported_finsupp_equiv` with the inverse of
  `chain_complex_x_iso_finsupp`.
-/

namespace Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexBasic

/-- The equivalence between continuous maps `T → X` whose range lies in a set `A ⊆ X` and
continuous maps `T → ↥A`, corestricting a map into `A` and postcomposing with the inclusion in
the other direction. -/
def continuous_map_range_subset_equiv
    {T X : Type} [TopologicalSpace T] [TopologicalSpace X] (A : Set X) :
    {f : C(T, X) | Set.range f ⊆ A} ≃ C(T, ↥A) :=
  { toFun := fun f => ⟨fun t => ⟨f.1 t, f.2 ⟨t, rfl⟩⟩, f.1.continuous.subtype_mk _⟩
    invFun := fun g =>
      ⟨⟨fun t => (g t : X), continuous_subtype_val.comp g.continuous⟩, by
        rintro _ ⟨t, rfl⟩; exact (g t).2⟩
    left_inv := fun f => by ext t; rfl
    right_inv := fun g => by ext t; rfl }

/-- For a topological space `X`, a set `A : Set X`, and `n : ℕ`, the singular `n`-simplices of
`X` supported in `A` (i.e. the degree-`n` term of `singular_subcomplex_of_set X A`) correspond
bijectively to the singular `n`-simplices of the subspace `A`. Rewriting both endpoints through
`toSSetObjEquiv` reduces this to `continuous_map_range_subset_equiv`, which carries the
topological content. -/
noncomputable def subspace_supported_simplex_bijection
    (X : TopCat.{0}) (A : Set X) (n : ℕ) :
    ↥((Library.AlgebraicTopology.MayerVietoris.ShortExactComplex.singular_subcomplex_of_set
        X A).obj (Opposite.op (SimplexCategory.mk n)))
      ≃ ((TopCat.toSSet.obj (TopCat.of A)).obj (Opposite.op (SimplexCategory.mk n))) := by
  refine (Equiv.subtypeEquiv (X.toSSetObjEquiv (Opposite.op (SimplexCategory.mk n)))
      (q := fun f : C(stdSimplex ℝ (Fin (n + 1)), X) => Set.range ⇑f ⊆ A)
      (fun σ => Iff.rfl)).trans ?_
  exact (continuous_map_range_subset_equiv A).trans
    ((TopCat.of A).toSSetObjEquiv (Opposite.op (SimplexCategory.mk n))).symm

variable {R : Type} [Ring R] (X : TopCat.{0}) (A : Set X) (n : ℕ)

/-- The linear equivalence identifying the submodule of `R`-chains on `X` supported in `A` in
degree `n` with the free `R`-module on the singular `n`-simplices of `A`. It is obtained by
turning the supported submodule into a `Finsupp` on that subtype
(`Finsupp.supportedEquivFinsupp`) and transporting along `subspace_supported_simplex_bijection`
(`Finsupp.domLCongr`). -/
noncomputable def subspace_supported_finsupp_equiv :
    Finsupp.supported R R
        ((Library.AlgebraicTopology.MayerVietoris.ShortExactComplex.singular_subcomplex_of_set
          X A).obj (Opposite.op (SimplexCategory.mk n)))
      ≃ₗ[R] ((TopCat.toSSet.obj (TopCat.of A)).obj (Opposite.op (SimplexCategory.mk n)) →₀ R) := by
  have e := subspace_supported_simplex_bijection X A n
  exact (Finsupp.supportedEquivFinsupp _) ≪≫ₗ (Finsupp.domLCongr e)

/-- The degree-`n` term of the supported subcomplex of the singular chain complex of `X`
associated to `A` is isomorphic, as an `R`-module, to the degree-`n` term of the singular chain
complex of the subspace `A`. This follows from `subspace_supported_finsupp_equiv`, transported
along `chain_complex_x_iso_finsupp`. -/
noncomputable def subspace_supported_x_iso :
    (Library.AlgebraicTopology.MayerVietoris.ShortExactComplex.supported_chain_complex (R := R)
        (TopCat.toSSet.obj X)
        (Library.AlgebraicTopology.MayerVietoris.ShortExactComplex.singular_subcomplex_of_set
          X A)).X n ≅
      ((TopCat.toSSet.obj (TopCat.of A)).chainComplex (ModuleCat.of R R)).X n := by
  have h := subspace_supported_finsupp_equiv (R := R) X A n
  exact h.toModuleIso ≪≫
    (Library.AlgebraicTopology.MayerVietoris.ShortExactComplex.chain_complex_x_iso_finsupp
      (TopCat.toSSet.obj (TopCat.of A)) n).symm

/-- `subspace_supported_finsupp_equiv` sends the generator of a supported simplex `σ` to the
generator of the corresponding `A`-simplex under `subspace_supported_simplex_bijection`. -/
theorem subspace_supported_finsupp_equiv_single
    (σ : ↥((Library.AlgebraicTopology.MayerVietoris.ShortExactComplex.singular_subcomplex_of_set
        X A).obj (Opposite.op (SimplexCategory.mk n))))
    (hσ : (Finsupp.single (↑σ) 1 : _ →₀ R) ∈ Finsupp.supported R R
      ((Library.AlgebraicTopology.MayerVietoris.ShortExactComplex.singular_subcomplex_of_set
        X A).obj (Opposite.op (SimplexCategory.mk n)))) :
    subspace_supported_finsupp_equiv (R := R) X A n ⟨Finsupp.single (↑σ) 1, hσ⟩
      = Finsupp.single (subspace_supported_simplex_bijection X A n σ) 1 := by
  classical
  rw [subspace_supported_finsupp_equiv, ← LinearEquiv.eq_symm_apply,
    LinearEquiv.trans_symm, LinearEquiv.trans_apply, Finsupp.domLCongr_symm,
    Finsupp.domLCongr_single, Equiv.symm_apply_apply]
  apply Subtype.ext
  rw [Finsupp.supportedEquivFinsupp_symm_single]

/-- `subspace_supported_simplex_bijection` commutes with the simplicial face maps `δ i`: taking
the `i`-th face of `σ` in `X` before applying the bijection agrees with applying the bijection
first and taking the `i`-th face in `A`. -/
theorem subspace_supported_simplex_bijection_face
    (i : Fin (n + 2))
    (σ : ↥((Library.AlgebraicTopology.MayerVietoris.ShortExactComplex.singular_subcomplex_of_set
        X A).obj (Opposite.op (SimplexCategory.mk (n + 1)))))
    (hmem : (TopCat.toSSet.obj X).δ i
          (σ : (TopCat.toSSet.obj X).obj (Opposite.op (SimplexCategory.mk (n + 1))))
        ∈ (Library.AlgebraicTopology.MayerVietoris.ShortExactComplex.singular_subcomplex_of_set
          X A).obj (Opposite.op (SimplexCategory.mk n))) :
    subspace_supported_simplex_bijection X A n ⟨(TopCat.toSSet.obj X).δ i ↑σ, hmem⟩
      = (TopCat.toSSet.obj (TopCat.of A)).δ i
          (subspace_supported_simplex_bijection X A (n + 1) σ) := by
  -- Cancel the codomain equiv `(of A).toSSetObjEquiv` via injectivity, then check pointwise:
  -- both sides evaluate at `z` to the same corestriction of `X.toSSetObjEquiv σ` precomposed
  -- with the topological face map, since `.δ i` on `toSSet.obj X` and `toSSet.obj (of A)` agree
  -- (`toSSetObjEquiv_δ_apply`).
  apply ((TopCat.of A).toSSetObjEquiv (Opposite.op (SimplexCategory.mk n))).injective
  ext z
  rfl

/-- The forward map of `subspace_supported_x_iso` unfolds as the composite of the module
isomorphism induced by `subspace_supported_finsupp_equiv` with the inverse of
`chain_complex_x_iso_finsupp`. This exposes the tactic-built isomorphism in a form that can be
rewritten along downstream. -/
theorem subspace_supported_x_iso_hom_eq :
    (subspace_supported_x_iso (R := R) X A n).hom =
      CategoryTheory.CategoryStruct.comp
        (subspace_supported_finsupp_equiv (R := R) X A n).toModuleIso.hom
        (Library.AlgebraicTopology.MayerVietoris.ShortExactComplex.chain_complex_x_iso_finsupp
          (TopCat.toSSet.obj (TopCat.of A)) n).inv := by
  rfl

end Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexBasic
