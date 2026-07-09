import Library.AlgebraicTopology.MayerVietoris.AffineHomotopy
import Library.AlgebraicTopology.MayerVietoris.ShortExactComplex

/-!
# Singular chain homotopy for barycentric subdivision

This file transports the affine barycentric-subdivision chain homotopy of
`AffineHomotopy` to singular chains, via the transport morphism
`singular_transport σ` associated to a singular simplex `σ : (toSSet.obj X) _⦋n⦌`.
This morphism realizes standard-simplex-supported affine chains as singular
chains of `X`, "seen through `σ`".

## Main statements

* `singular_transport_face`: `singular_transport` is compatible with the face
  maps of the ambient simplicial set.
* `singular_sd_boundary`: the singular subdivision operator `singular_sd` is a
  chain map, `∂ ∘ S = S ∘ ∂`.
* `singular_ht_boundary`: `singular_ht` realizes Hatcher's chain-homotopy
  identity `∂T + T∂ = id − S` between the identity and the singular
  subdivision, transported from the affine identity `affine_ht_boundary`.

Most of the intermediate lemmas factor these two chain-map identities through
`singular_transport σ`, matching each singular boundary term against its
affine counterpart pushed forward along the transport.

## Implementation notes

Most of the file works generator-by-generator on `Finsupp.single σ 1`, using
`Finsupp.lhom_ext'` / `linear_eq_on_supported` to reduce `R`-linear map
identities to their action on generators (resp. on `Finsupp.supported`
submodules), and `Finsupp.lmapDomain` / `Finsupp.subtypeDomain` to move chains
between the singular and affine levels.
-/

open CategoryTheory Simplicial
open Library.AlgebraicTopology.MayerVietoris.AffineHomotopy
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex

namespace Library.AlgebraicTopology.MayerVietoris.SingularSubdivisionHomotopy

/-- Evaluating the transport morphism of `σ` on the fundamental vertex tuple recovers `σ`.
Work through the equiv `X.toSSetObjEquiv`; pointwise (`ext z`) the composite splits: naturality
of `toSSetObjEquiv` under `toSSet.map` turns the `toSSet.map` layer into postcomposition with
`σ`'s underlying map, and the affine realization of the identity vertex tuple is the identity
chart, so the argument reduces to `z`. -/
theorem singular_transport_fund {X : TopCat.{0}} {n : ℕ}
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (h : Set.range (fun k => (Pi.single k 1 : Fin (n + 1) → ℝ))
      ⊆ stdSimplex ℝ (Fin (n + 1))) :
    (singular_transport σ).app (Opposite.op ⦋n⦌)
        ⟨fun k => (Pi.single k 1 : Fin (n + 1) → ℝ), h⟩ = σ  := by
  apply (X.toSSetObjEquiv (Opposite.op ⦋n⦌)).injective
  ext z
  simp only [singular_transport, NatTrans.comp_app_apply]
  have h1 : ∀ (Y : TopCat.{0}) (g : C(Y, X)) (N : SimplexCategoryᵒᵖ)
      (y : (TopCat.toSSet.obj Y).obj N) (w : stdSimplex ℝ (Fin (N.unop.len + 1))),
      X.toSSetObjEquiv N ((TopCat.toSSet.map (TopCat.ofHom g)).app N y) w
        = g (Y.toSSetObjEquiv N y w) := fun Y g N y w => toSSetObjEquiv_map_naturality g N y w
  have h2 : (TopCat.of (stdSimplex ℝ (Fin (n + 1)) : Set (Fin (n + 1) → ℝ))).toSSetObjEquiv
        (Opposite.op ⦋n⦌)
        ((affine_subcomplex_realization (convex_stdSimplex ℝ (Fin (n + 1)))).app (Opposite.op ⦋n⦌)
          ⟨fun k => (Pi.single k 1 : Fin (n + 1) → ℝ), h⟩) z = z :=
    affine_subcomplex_realization_apply_eq_self h z
  rw [h1 (TopCat.of ↑(stdSimplex ℝ (Fin (n + 1)))) (X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ)
      (Opposite.op ⦋n⦌) _ z, h2]

/-- Point evaluation of `singular_transport τ`: unfold the transport composite
(the corestricted affine realization ≫ `toSSet.map (ofHom (toSSetObjEquiv τ))`), split the
`.app` of the composite (`NatTrans.comp_app` + `ConcreteCategory.comp_apply`), then peel the
`toSSet.map` layer under `toSSetObjEquiv` via its naturality lemma
`toSSetObjEquiv_map_naturality`. The residual — evaluating the corestricted affine realization
at `z` — is definitional, so `erw` closes the goal by `rfl`. -/
theorem singular_transport_app_eval
    {X : TopCat.{0}} {k m : ℕ} (τ : (TopCat.toSSet.obj X) _⦋k⦌)
    (u : {v : (affine_sset (Fin (k + 1) → ℝ)) _⦋m⦌ //
        Set.range v ⊆ stdSimplex ℝ (Fin (k + 1))})
    (z : stdSimplex ℝ (Fin (m + 1))) :
    (X.toSSetObjEquiv (Opposite.op ⦋m⦌)) ((singular_transport τ).app (Opposite.op ⦋m⦌) u) z =
      (X.toSSetObjEquiv (Opposite.op ⦋k⦌)) τ
        ⟨affine_simplex_map u.1 z,
          affine_simplex_map_mem_of_convex (convex_stdSimplex ℝ (Fin (k + 1))) u.2 z⟩  := by
  simp only [singular_transport, NatTrans.comp_app, ConcreteCategory.comp_apply]
  erw [toSSetObjEquiv_map_naturality]

/-- Face-compatibility of `singular_transport`: split into (1) a general app/point evaluation
`singular_transport_app_eval` that unfolds the corestricted affine realization ≫ pushforward
down to `toSSetObjEquiv τ ⟨affine_simplex_map u.1 z, _⟩`, and (2) the pure geometric core
`singular_transport_face_core`. After proving both sides equal via `toSSetObjEquiv.injective` +
`ContinuousMap.ext`, rewrite each side by the evaluation lemma, then close by the core. -/
theorem singular_transport_face
    {X : TopCat.{0}} {n : ℕ} (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌)
    (i : Fin (n + 2)) {m : ℕ}
    (w : {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ //
        Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))})
    (hw : Set.range (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘ w.1) ⊆
        stdSimplex ℝ (Fin (n + 2))) :
    (singular_transport ((TopCat.toSSet.obj X).δ i σ)).app (Opposite.op ⦋m⦌) w =
      (singular_transport σ).app (Opposite.op ⦋m⦌)
        ⟨⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘ w.1, hw⟩  := by
  apply (X.toSSetObjEquiv (Opposite.op ⦋m⦌)).injective
  ext z
  rw [singular_transport_app_eval, singular_transport_app_eval]
  exact singular_transport_face_core σ i w hw z

/-- Transport `affine_ht_boundary` along the pushforward
`lmapDomain (singular_transport σ) ∘ subtypeDomain (…)`, applied to the fundamental tuple.
`hx` instantiates the affine identity `∂T (n+1) + T n ∂ = id − S` on the fundamental tuple; `hF`
is the additivity of the pushforward (`Finsupp.subtypeDomain_add` + `map_add`, via `erw` since
the domain type is only defeq, not syntactically, to `singular_transport`'s codomain);
`rw [hF, hx]` folds the two pushforward terms and rewrites through `hx`. -/
theorem singular_ht_boundary_affine_combine {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
          ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
            (affine_ht (R := R) (n + 1)
              (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))
      + Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
          (affine_ht (R := R) n
            ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
                • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
              (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
          ((Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1
                : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ →₀ R)
            - affine_sd (R := R) (n + 1)
              (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))) := by
  have key := affine_ht_boundary (R := R) (E := Fin (n + 2) → ℝ) n
  have hx := LinearMap.congr_fun key
    (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1)
  simp only [LinearMap.add_apply, LinearMap.sub_apply, LinearMap.comp_apply,
    LinearMap.id_apply] at hx
  have hF : ∀ a b : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ →₀ R,
      Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2))) a)
        + Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2))) b)
        = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2))) (a + b)) := by
    intro a b
    erw [Finsupp.subtypeDomain_add, map_add]
  rw [hF, hx]

/-- Pushes the singular subdivision `S` through the alternating face-sum boundary via
`lmapdomain_sum_on_generator` (LHS half of the chain-map identity `S ∘ ∂ = ∂ ∘ S`).
`lmapdomain_sum_on_generator` gives, on the generator `single σ 1`, that
`(∑ i, (-1)^i • lmapDomain (δ i)) (single σ 1) = ∑ i, (-1)^i • single (δ i σ) 1`
(applying the linear-map equality at ring element `1`); pushing `singular_sd`
(an `R`-linear map) through the resulting sum via `map_sum`/`map_zsmul`
(the `(-1)^i` coefficients are `ℤ`-scalars, not `R`) matches the goal's RHS. -/
theorem singular_sd_lhs_face_sum {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    singular_sd (R := R) n
        ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
            • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
          (Finsupp.single σ 1))
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • singular_sd (R := R) n (Finsupp.single ((TopCat.toSSet.obj X).δ i σ) 1) := by
  have h1 := LinearMap.congr_fun
    (lmapdomain_sum_on_generator (R := R) (TopCat.toSSet.obj X) n σ) 1
  simp only [LinearMap.comp_apply, Finsupp.lsingle_apply, LinearMap.sum_apply,
    LinearMap.smul_apply] at h1
  simp only [LinearMap.sum_apply, LinearMap.smul_apply, h1, map_sum, map_zsmul]

/-- Pushes the transported affine subdivision through the alternating face-sum boundary
(mid half of the chain-map identity `S ∘ ∂ = ∂ ∘ S`, factored through `singular_transport σ`).
`lmapdomain_sum_on_generator` (on `affine_sset (Fin (n+2) → ℝ)` at the generator
`single (fun i => Pi.single i 1) 1`, applied at ring element `1`) turns the affine
alternating face-sum into `∑ i, (-1)^i • single (δ i g) 1`; the composite
`lmapDomain ∘ subtypeDomain ∘ affine_sd` is `AddMonoidHom`-additive, so bundling it
as `F` and applying `map_sum`/`map_zsmul` distributes it across the sum, matching the RHS. -/
theorem singular_sd_mid_face_sum {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (affine_sd (R := R) n
              ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
                  • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
              (Finsupp.subtypeDomain
                (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
                  Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
                (affine_sd (R := R) n
                  (Finsupp.single ((affine_sset (Fin (n + 2) → ℝ)).δ i
                      (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ))) 1)))  := by
  have h := lmapdomain_sum_on_generator (R := R) (affine_sset (Fin (n + 2) → ℝ)) n
    (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ))
  have h1 := LinearMap.congr_fun h 1
  simp only [LinearMap.comp_apply, Finsupp.lsingle_apply, LinearMap.sum_apply,
    LinearMap.smul_apply] at h1
  simp only [LinearMap.sum_apply, LinearMap.smul_apply]
  rw [h1]
  set F : ((affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ →₀ R) →+
      ((TopCat.toSSet.obj X) _⦋n⦌ →₀ R) :=
    (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))).toAddMonoidHom.comp
      ((Finsupp.subtypeDomainAddMonoidHom
          (M := R) (p := fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))).comp
        (affine_sd (R := R) n).toAddMonoidHom) with hF
  have hcomp : ∀ v, Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
      (Finsupp.subtypeDomain
        (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
        (affine_sd (R := R) n v)) = F v := fun v => rfl
  simp only [hcomp]
  rw [map_sum]
  simp only [map_zsmul]

/-- Direct analogue of `singular_sd_lhs_face_sum` for `singular_ht`: push the alternating
face-sum boundary through the `R`-linear `singular_ht`.
`lmapdomain_sum_on_generator` gives `(∑ i, (-1)^i • lmapDomain (δ i)) (single σ 1)
= ∑ i, (-1)^i • single (δ i σ) 1`; then `map_sum`/`map_zsmul` push `singular_ht`
through the ℤ-scalar sum to match the RHS. -/
theorem singular_ht_lhs_face_sum {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    @singular_ht R _ X n
        ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) (Finsupp.single σ 1))
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • @singular_ht R _ X n (Finsupp.single ((TopCat.toSSet.obj X).δ i σ) 1)  := by
  have h := lmapdomain_sum_on_generator (R := R) (TopCat.toSSet.obj X) n σ
  have h1 := LinearMap.congr_fun h 1
  simp only [LinearMap.comp_apply, Finsupp.lsingle_apply, LinearMap.sum_apply,
    LinearMap.smul_apply] at h1
  simp only [LinearMap.sum_apply, LinearMap.smul_apply]
  rw [h1, map_sum]
  simp only [map_zsmul]

/-- Distribute the composite `lmapDomain (transport) ∘ subtypeDomain ∘ affine_ht n`
over the pushed affine boundary sum on the vertex generator.
`heq` (cites the proved `lmapdomain_sum_on_generator`): the sum-of-faces linear map applied
to the generator equals `∑ i, (-1)^i • single (δ i v) 1`.

Then push each layer through the ℤ-scalar sum: `affine_ht` and `subtypeDomain` distribute via
`map_sum`/`map_zsmul`/`subtypeDomain_sum`/`hsd` (clean coes), while the outer
`lmapDomain (transport)` needs `erw` + the concrete-headed `hlm` because the
`ConcreteCategory.hom` coercion on `singular_transport` blocks `rw`/`simp` matching. -/
theorem singular_ht_mid_face_sum {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (affine_ht (R := R) n
              ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
                  • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
              (Finsupp.subtypeDomain
                (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
                  Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
                (affine_ht (R := R) n
                  (Finsupp.single ((affine_sset (Fin (n + 2) → ℝ)).δ i
                      (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ))) 1)))  := by
  have heq : (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
        • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
        (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1)
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • Finsupp.single ((affine_sset (Fin (n + 2) → ℝ)).δ i
              (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ))) 1 := by
    have h1 := LinearMap.congr_fun (lmapdomain_sum_on_generator (R := R)
      (affine_sset (Fin (n + 2) → ℝ)) n (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ))) 1
    simpa only [LinearMap.comp_apply, LinearMap.sum_apply, LinearMap.smul_apply,
      Finsupp.lsingle_apply] using h1
  have hsd : ∀ (c : ℤ) (y : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ →₀ R),
      Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 2))) (c • y)
        = c • Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2))) y :=
    fun c y => map_zsmul (Finsupp.subtypeDomainAddMonoidHom (M := R)
      (p := fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
        Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))) c y
  have hlm : ∀ (c : ℤ) (z : (Subtype (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
        Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))) →₀ R),
      Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌)) (c • z)
        = c • Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌)) z :=
    fun c z => map_zsmul (Finsupp.lmapDomain R R
      ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))) c z
  rw [heq, map_sum (affine_ht (R := R) n)]
  simp only [map_zsmul]
  rw [Finsupp.subtypeDomain_sum]
  simp only [hsd]
  erw [map_sum (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌)))]
  simp only [hlm]

/-- The fundamental affine tuple transports to `σ` itself.
`affine_simplex_map_single_tuple` shows the identity vertex tuple realizes to the
identity map, so `singular_transport_app_eval` (naturality of the singular transport)
collapses `(singular_transport σ).app _ ⟨fundamental, hw⟩` back to `σ` pointwise via
`X.toSSetObjEquiv` injectivity; `Finsupp.mapDomain_single` then pushes this through
`lmapDomain`/`subtypeDomain` on the single generator. -/
theorem singular_transport_fund_single {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
          (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))
      = Finsupp.single σ 1 := by
  have hw : Set.range (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) ⊆
      stdSimplex ℝ (Fin (n + 2)) := by
    rintro _ ⟨i, rfl⟩
    exact single_mem_stdSimplex ℝ i
  have hsub :
      Finsupp.subtypeDomain (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
        (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) (1 : R))
      = Finsupp.single
          (⟨fun i => (Pi.single i 1 : Fin (n + 2) → ℝ), hw⟩ :
            {v : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ //
              Set.range v ⊆ stdSimplex ℝ (Fin (n + 2))}) (1 : R) := by
    classical
    apply Finsupp.ext
    intro a
    simp only [Finsupp.subtypeDomain_apply, Finsupp.single_apply, Subtype.ext_iff]
  rw [hsub, Finsupp.lmapDomain_apply]
  have hmd : Finsupp.mapDomain (⇑((singular_transport σ).app (Opposite.op ⦋n + 1⦌)))
      (Finsupp.single
        (⟨fun i => (Pi.single i 1 : Fin (n + 2) → ℝ), hw⟩ :
          {v : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ //
            Set.range v ⊆ stdSimplex ℝ (Fin (n + 2))}) (1 : R))
      = Finsupp.single (((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          ⟨fun i => (Pi.single i 1 : Fin (n + 2) → ℝ), hw⟩) (1 : R) :=
    Finsupp.mapDomain_single
  refine hmd.trans ?_
  congr 1
  apply (X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌)).injective
  apply ContinuousMap.ext
  intro z
  have hz := singular_transport_app_eval σ
    (⟨fun i => (Pi.single i 1 : Fin (n + 2) → ℝ), hw⟩ :
      {v : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ //
        Set.range v ⊆ stdSimplex ℝ (Fin (n + 2))}) z
  exact hz.trans (congrArg (fun p => (X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌)) σ p)
    (Subtype.ext (affine_simplex_map_single_tuple z)))

/-- Transport of the affine chain-homotopy RHS `(id − S)` on the fundamental tuple
equals the singular RHS `single σ 1 − S (single σ 1)`.
`singular_transport_fund_single` gives the `id`-part: the transported fundamental
tuple is `single σ 1`; linearity (`subtypeDomain_sub` + `lmapDomain.map_sub`)
distributes over the subtraction, and the `affine_sd`-part is `singular_sd`'s
generator value by definition (`linearCombination_single`). -/
theorem singular_ht_boundary_transport_rhs {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
          ((Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1
                : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ →₀ R)
            - affine_sd (R := R) (n + 1)
              (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1)))
      = Finsupp.single σ 1 - @singular_sd R _ X (n + 1) (Finsupp.single σ 1)  := by
  have h_fund := singular_transport_fund_single (R := R) (X := X) n σ
  have hlin := (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))).map_sub
    (Finsupp.subtypeDomain
        (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
        (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))
    (Finsupp.subtypeDomain
        (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
        (affine_sd (R := R) (n + 1)
          (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1)))
  rw [Finsupp.subtypeDomain_sub]
  refine hlin.trans ?_
  rw [h_fund]
  congr 1
  simp only [singular_sd, Finsupp.linearCombination_single, one_smul]

/-- `affine_sd` naturality (`affine_sd_map`) transported to a
vertex-face generator, i.e. the fundamental δ-face chain of dimension `n+1`
equals the vertex-pushforward (along `Fin.succAbove i`) of the fundamental
`n`-chain.
`hface` identifies the δ-face generator with `g ∘ (id_{n+1})` by unfolding
`affine_sset.δ` (defeq to precomposition with `succAbove`) and
`FunOnFinite.linearMap_piSingle`; `hgen` restates that generator identity as
an `lmapDomain` pushforward via `Finsupp.mapDomain_single`; combining with
`affine_sd_map` applied to the fundamental `n`-generator closes the goal. -/
theorem affine_sd_face_eq {R : Type} [Ring R] (n : ℕ) (i : Fin (n + 2)) :
    affine_sd (R := R) n
        (Finsupp.single ((affine_sset (Fin (n + 2) → ℝ)).δ i
            (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ))) 1)
      = Finsupp.lmapDomain R R
          (fun v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v :
              (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌))
          (affine_sd (R := R) n
            (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1)) := by
  have hface : (affine_sset (Fin (n + 2) → ℝ)).δ i
      (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ))
      = (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘
          (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) :
          (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌) := by
    funext j
    change (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ)) (i.succAbove j) = _
    simp [FunOnFinite.linearMap_piSingle]
  have hnat := affine_sd_map (R := R) (FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) n
  have hgen : Finsupp.single
      (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘
          (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌)
      (1 : R)
      = Finsupp.lmapDomain R R
          (fun v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v :
              (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌))
          (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1) := by
    rw [Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
  rw [hface]
  exact (congrArg (affine_sd (R := R) n) hgen).trans (DFunLike.congr_fun hnat _)

/-- Unfold `singular_sd` (a `Finsupp.linearCombination`) on the
generator `single τ 1` via `Finsupp.linearCombination_single` + `one_smul`. -/
theorem singular_sd_single_gen {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (τ : (TopCat.toSSet.obj X) _⦋n⦌) :
    singular_sd (R := R) n (Finsupp.single τ 1)
      = Finsupp.lmapDomain R R ((singular_transport τ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (affine_sd (R := R) n
              (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1))) := by
  unfold singular_sd
  rw [Finsupp.linearCombination_single, one_smul]

/-- Face-compatibility of the affine cone homotopy `affine_ht` on a single vertex-face
generator: the δ-face of the fundamental (n+2)-tuple hit by `affine_ht n` equals the
vertex-pushforward (along `i.succAbove`) of `affine_ht n` on the fundamental
(n+1)-tuple. Direct analog of the proved sibling `affine_sd_face_eq`, with the
affine naturality `affine_ht_map` replacing `affine_sd_map`. -/
theorem affine_ht_single_face_pushforward {R : Type} [Ring R] (n : ℕ) (i : Fin (n + 2)) :
    affine_ht (R := R) n
        (Finsupp.single ((affine_sset (Fin (n + 2) → ℝ)).δ i
            (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ))) 1)
      = Finsupp.lmapDomain R R
          (fun v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n + 1⦌ =>
            (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘ v
              : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌))
          (affine_ht (R := R) n
            (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1))  := by
  have hface : (affine_sset (Fin (n + 2) → ℝ)).δ i
      (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ))
      = (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘
          (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) :
          (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌) := by
    funext j
    change (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ)) (i.succAbove j) = _
    simp [FunOnFinite.linearMap_piSingle]
  have hnat := affine_ht_map (R := R) (FunOnFinite.linearMap ℝ ℝ i.succAbove) n
  have hgen : Finsupp.single
      (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘
          (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌)
      (1 : R)
      = Finsupp.lmapDomain R R
          (fun v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘ v :
              (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌))
          (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1) := by
    rw [Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
  rw [hface]
  exact (congrArg (affine_ht (R := R) n) hgen).trans (DFunLike.congr_fun hnat _)

/-- The singular boundary sum commutes with
`lmapDomain (T.app _)` for any simplicial map `T : A ⟶ B`, via `NatTrans.naturality_apply`.
Each degree-`i` term `B.δ i ∘ T.app (m+1) = T.app m ∘ A.δ i` is pure functor naturality
of `T` at the face morphism `(SimplexCategory.δ i).op`; `lmapDomain_comp` folds the two
`lmapDomain` compositions on each side into that single function-level identity. -/
theorem boundary_natural_transport_sset {R : Type} [Ring R] {A B : SSet.{0}}
    (T : A ⟶ B) (m : ℕ) (x : ((A _⦋m + 1⦌) →₀ R)) :
    (∑ i : Fin (m + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R (B.δ i))
        (Finsupp.lmapDomain R R (T.app (Opposite.op ⦋m + 1⦌)) x)
      = Finsupp.lmapDomain R R (T.app (Opposite.op ⦋m⦌))
          ((∑ i : Fin (m + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R (A.δ i)) x) := by
  have hnat : ∀ (i : Fin (m + 2)) (y : A _⦋m + 1⦌),
      T.app (Opposite.op ⦋m⦌) (A.δ i y) = B.δ i (T.app (Opposite.op ⦋m + 1⦌) y) := by
    intro i y
    simp [SimplicialObject.δ, NatTrans.naturality_apply T (SimplexCategory.δ i).op y]
  simp only [LinearMap.sum_apply, LinearMap.smul_apply]
  rw [map_sum]
  refine Finset.sum_congr rfl (fun i _ => ?_)
  rw [map_zsmul]
  congr 1
  rw [← LinearMap.comp_apply, ← LinearMap.comp_apply, ← Finsupp.lmapDomain_comp,
    ← Finsupp.lmapDomain_comp]
  have hfun : (⇑(ConcreteCategory.hom (SimplicialObject.δ B i)) ∘
        ⇑(ConcreteCategory.hom (T.app (Opposite.op ⦋m + 1⦌)))) =
      (⇑(ConcreteCategory.hom (T.app (Opposite.op ⦋m⦌))) ∘
        ⇑(ConcreteCategory.hom (SimplicialObject.δ A i))) :=
    funext fun y => (hnat i y).symm
  rw [hfun]

/-- Per-face commutation of the affine boundary with `subtypeDomain` onto the
subcomplex of `s`-valued tuples. The subcomplex face map is definitionally the
ambient one restricted (`val ∘ δ_sub = δ ∘ val`, `hcompat`, by `rfl`), so the
claim is a `Finsupp.mapDomain`/`subtypeDomain` naturality: `mapDomain val`
recovers a subtype-supported chain (`hrecover`), pushing `subtypeDomain p c`
forward along `val` returns `c` since `c` is `s`-supported (`hstep2`, uses
`hc`), and `mapDomain_comp` + `hcompat` assemble these into `key`. -/
theorem affine_face_subtype_domain_comm {R : Type} [Ring R] {E : Type}
    [AddCommGroup E] [Module ℝ E] (s : Set E) (m : ℕ) (i : Fin (m + 2))
    (c : (affine_sset E) _⦋m + 1⦌ →₀ R)
    (hc : c ∈ Finsupp.supported R R {w : (affine_sset E) _⦋m + 1⦌ | Set.range w ⊆ s}) :
    Finsupp.lmapDomain R R ((affine_subcomplex_of_set s : SSet).δ i)
        (Finsupp.subtypeDomain (fun w : (affine_sset E) _⦋m + 1⦌ => Set.range w ⊆ s) c)
      = Finsupp.subtypeDomain (fun w : (affine_sset E) _⦋m⦌ => Set.range w ⊆ s)
          (Finsupp.lmapDomain R R ((affine_sset E).δ i) c)  := by
  rw [Finsupp.lmapDomain_apply, Finsupp.lmapDomain_apply]
  -- underlying face maps agree: `val ∘ δ_sub = δ ∘ val`
  have hcompat :
      ((Subtype.val : {w : (affine_sset E) _⦋m⦌ // Set.range w ⊆ s} → _) ∘
        ⇑(ConcreteCategory.hom (SimplicialObject.δ (affine_subcomplex_of_set s).toSSet i)))
      = (⇑(ConcreteCategory.hom (SimplicialObject.δ (affine_sset E) i)) ∘
        (Subtype.val : {w : (affine_sset E) _⦋m + 1⦌ // Set.range w ⊆ s} → _)) := by
    funext a; rfl
  -- `subtypeDomain q ∘ mapDomain val = id`
  have hrecover : ∀ h : {w : (affine_sset E) _⦋m⦌ // Set.range w ⊆ s} →₀ R,
      Finsupp.subtypeDomain (fun w => Set.range w ⊆ s)
          (Finsupp.mapDomain (Subtype.val : {w : (affine_sset E) _⦋m⦌ // Set.range w ⊆ s} → _) h)
        = h := by
    intro h; ext b
    rw [Finsupp.subtypeDomain_apply]
    exact Finsupp.mapDomain_apply Subtype.val_injective h b
  -- pushing `subtypeDomain p c` forward along `val` recovers `c` (uses `hc`)
  have hstep2 :
      Finsupp.mapDomain (Subtype.val : {w : (affine_sset E) _⦋m + 1⦌ // Set.range w ⊆ s} → _)
        (Finsupp.subtypeDomain (fun w : (affine_sset E) _⦋m + 1⦌ => Set.range w ⊆ s) c) = c := by
    ext a
    by_cases ha : Set.range a ⊆ s
    · have := Finsupp.mapDomain_apply
        (f := (Subtype.val : {w : (affine_sset E) _⦋m + 1⦌ // Set.range w ⊆ s} → _))
        Subtype.val_injective (Finsupp.subtypeDomain _ c) ⟨a, ha⟩
      simpa [Finsupp.subtypeDomain_apply] using this
    · rw [Finsupp.mapDomain_notin_range]
      · exact ((Finsupp.mem_supported' R c).mp hc a ha).symm
      · rw [Subtype.range_coe_subtype]; exact ha
  -- assemble via `mapDomain_comp`
  have key :
      Finsupp.mapDomain (Subtype.val : {w : (affine_sset E) _⦋m⦌ // Set.range w ⊆ s} → _)
        (Finsupp.mapDomain
            ⇑(ConcreteCategory.hom (SimplicialObject.δ (affine_subcomplex_of_set s).toSSet i))
          (Finsupp.subtypeDomain (fun w : (affine_sset E) _⦋m + 1⦌ => Set.range w ⊆ s) c))
      = Finsupp.mapDomain ⇑(ConcreteCategory.hom (SimplicialObject.δ (affine_sset E) i)) c := by
    conv_rhs => rw [← hstep2, ← Finsupp.mapDomain_comp]
    rw [← Finsupp.mapDomain_comp, hcompat]
    rfl
  have hfin :
      Finsupp.subtypeDomain (fun w : (affine_sset E) _⦋m⦌ => Set.range w ⊆ s)
          (Finsupp.mapDomain ⇑(ConcreteCategory.hom (SimplicialObject.δ (affine_sset E) i)) c)
        = Finsupp.mapDomain
            ⇑(ConcreteCategory.hom (SimplicialObject.δ (affine_subcomplex_of_set s).toSSet i))
            (Finsupp.subtypeDomain (fun w : (affine_sset E) _⦋m + 1⦌ => Set.range w ⊆ s) c) := by
    rw [← key]
    exact hrecover _
  exact hfin.symm

/-- Boundary commutes with `subtypeDomain` onto the affine subcomplex of `s`.
Distribute both alternating sums (`LinearMap.sum_apply`) and `subtypeDomain`
over the RHS sum (`Finsupp.subtypeDomain_sum`), then match term-by-term via the
single per-face commutation `affine_face_subtype_domain_comm` (uses `hc`), with
the sign pulled through `subtypeDomain` as an additive `zsmul` map. -/
theorem affine_boundary_subtype_domain_comm {R : Type} [Ring R] {E : Type}
    [AddCommGroup E] [Module ℝ E] (s : Set E) (m : ℕ)
    (c : (affine_sset E) _⦋m + 1⦌ →₀ R)
    (hc : c ∈ Finsupp.supported R R {w : (affine_sset E) _⦋m + 1⦌ | Set.range w ⊆ s}) :
    (∑ i : Fin (m + 2), (-1 : ℤ) ^ (i : ℕ)
        • Finsupp.lmapDomain R R ((affine_subcomplex_of_set s : SSet).δ i))
        (Finsupp.subtypeDomain (fun w : (affine_sset E) _⦋m + 1⦌ => Set.range w ⊆ s) c)
      = Finsupp.subtypeDomain (fun w : (affine_sset E) _⦋m⦌ => Set.range w ⊆ s)
          ((∑ i : Fin (m + 2), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((affine_sset E).δ i)) c)  := by
  have hface : ∀ i : Fin (m + 2),
      Finsupp.lmapDomain R R ((affine_subcomplex_of_set s : SSet).δ i)
          (Finsupp.subtypeDomain (fun w : (affine_sset E) _⦋m + 1⦌ => Set.range w ⊆ s) c)
        = Finsupp.subtypeDomain (fun w : (affine_sset E) _⦋m⦌ => Set.range w ⊆ s)
            (Finsupp.lmapDomain R R ((affine_sset E).δ i) c) :=
    fun i => affine_face_subtype_domain_comm s m i c hc
  rw [LinearMap.sum_apply, LinearMap.sum_apply, Finsupp.subtypeDomain_sum]
  refine Finset.sum_congr rfl (fun i _ => ?_)
  rw [LinearMap.smul_apply, LinearMap.smul_apply, hface i]
  exact (map_zsmul (Finsupp.subtypeDomainAddMonoidHom
    (p := fun w : (affine_sset E) _⦋m⦌ => Set.range w ⊆ s) (M := R)) _ _).symm

/-- Boundary naturality of `singular_transport σ` on supported affine chains, general `c`.
Mirrors the fundamental-chain case (at `m := n`):
(1) `boundary_natural_transport_sset` commutes the singular boundary sum past
    `lmapDomain (T.app _)` for the abstract simplicial map `T := singular_transport σ`;
(2) `congrArg (lmapDomain (T.app op⦋n⦌))` reduces to the affine side;
(3) `affine_boundary_subtype_domain_comm` commutes the affine boundary
    past `subtypeDomain` on the supported chain `c` (support witness `hc`). -/
theorem singular_boundary_transport_naturality {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌)
    (c : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ →₀ R)
    (hc : c ∈ Finsupp.supported R R
        {w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ |
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 2))}) :
    (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
        (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2))) c))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
                • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i)) c))  := by
  refine (boundary_natural_transport_sset (singular_transport σ) n
      (Finsupp.subtypeDomain
        (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 2))) c)).trans ?_
  refine congrArg
    (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))) ?_
  exact affine_boundary_subtype_domain_comm (stdSimplex ℝ (Fin (n + 2))) n c hc

/-- Push the singular boundary of `S (single σ 1)` through the transport morphism.
(1) `hsd` unfolds `singular_sd (n+1) (single σ 1)` (a `linearCombination` on a
    generator) to `transport_* (subtypeDomain (affine_sd (n+1) (single fund 1)))`.
(2) `singular_boundary_transport_naturality` (the crux) commutes the singular
    boundary `∂_X` past the transport pushforward, landing on
    `transport_* (subtypeDomain (∂_affine (affine_sd (n+1) (single fund 1))))`.
(3) `haff` is the affine chain-map identity `∂ ∘ S = S ∘ ∂` (`affine_sd_boundary`)
    evaluated on the fundamental chain, closing the goal. -/
theorem singular_sd_boundary_transport_lhs {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
        (singular_sd (R := R) (n + 1) (Finsupp.single σ 1))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (affine_sd (R := R) n
              ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
                  • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))  := by
  have hsd : singular_sd (R := R) (n + 1) (Finsupp.single σ 1)
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (affine_sd (R := R) (n + 1)
              (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))) := by
    simp only [singular_sd, Finsupp.linearCombination_single, one_smul]
  have haff : (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
        (affine_sd (R := R) (n + 1)
          (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))
      = affine_sd (R := R) n
          ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
            (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1)) := by
    have h := LinearMap.congr_fun (affine_sd_boundary (R := R) (E := Fin (n + 2) → ℝ) n)
      (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1)
    simpa only [LinearMap.comp_apply] using h
  rw [hsd, singular_boundary_transport_naturality n σ _ (affine_sd_single_tuple_supported (n + 1)),
    haff]

/-- Naturality of the singular boundary sum against the transport pushforward
`lmapDomain (singular_transport σ).app`, on the specific chain `affine_ht (n+1) (fund)`:
degree-`(n+1)` instance of `boundary_natural_transport_sset` composed with
`affine_boundary_subtype_domain_comm` (support discharged by
`affine_ht_single_tuple_supported`). -/
theorem singular_ht_transport_boundary_nat {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
      (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
          (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 2⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 2⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
              (affine_ht (R := R) (n + 1)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))
        = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
              ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ)
                  • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
                (affine_ht (R := R) (n + 1)
                  (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))  := by
  refine (boundary_natural_transport_sset (singular_transport σ) (n + 1)
      (Finsupp.subtypeDomain
        (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 2⦌ =>
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
        (affine_ht (R := R) (n + 1)
          (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1)))).trans ?_
  refine congrArg
    (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))) ?_
  exact affine_boundary_subtype_domain_comm (stdSimplex ℝ (Fin (n + 2))) (n + 1)
    (affine_ht (R := R) (n + 1) (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))
    (affine_ht_single_tuple_supported (R := R) (n + 1))

/-- `∂T`-side of the singular chain homotopy: push the singular boundary through the
transport pushforward of `singular_ht (single σ 1)`.
`h_unfold` evaluates `singular_ht (n+1)` on the generator `single σ 1` via
`Finsupp.linearCombination_single`, exposing the transported affine chain
`affine_ht (n+1) (fundamental tuple)` at level `n+2`.
`h_nat` (`singular_ht_transport_boundary_nat`) is the naturality core: the
singular boundary sum commutes past `lmapDomain (singular_transport σ).app`
into the affine boundary sum (simplicial face-compatibility of `singular_transport`). -/
theorem singular_ht_boundary_dt_term {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
        (@singular_ht R _ X (n + 1) (Finsupp.single σ 1))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ)
                • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
              (affine_ht (R := R) (n + 1)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))  := by
  have h_unfold : (@singular_ht R _ X (n + 1) (Finsupp.single σ 1))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 2⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 2⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (affine_ht (R := R) (n + 1)
              (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))) := by
    simp only [singular_ht, singular_ht, Finsupp.linearCombination_single, one_smul]
  have h_nat := singular_ht_transport_boundary_nat (R := R) n σ
  rw [h_unfold]; exact h_nat

/-- Both `single v r`/`single (pushed v) r` restrictions vanish
when the range-in-stdSimplex support predicate fails at the generator, via
`Finsupp.subtypeDomain_eq_zero_iff'` + `Finsupp.single_eq_of_ne`, so both sides
of the transported-face equation reduce to `lmapDomain _ 0 = 0` by `map_zero`. -/
theorem transport_face_generator_neg {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) (i : Fin (n + 2))
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) (r : R)
    (hv : ¬ Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)))
    (hGv : ¬ Set.range (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v
        : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌) ⊆ stdSimplex ℝ (Fin (n + 2))) :
    Finsupp.lmapDomain R R
        ((singular_transport ((TopCat.toSSet.obj X).δ i σ)).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single v r))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (Finsupp.lmapDomain R R
              (fun v' : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v' :
                  (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌))
              (Finsupp.single v r))) := by
  have hL : (Finsupp.subtypeDomain
      (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ => Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
      (Finsupp.single v r)) = 0 := by
    rw [Finsupp.subtypeDomain_eq_zero_iff']
    intro x hpx
    by_cases hxv : x = v
    · subst hxv; exact absurd hpx hv
    · exact Finsupp.single_eq_of_ne hxv
  have hR : (Finsupp.subtypeDomain
      (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ => Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
      (Finsupp.single (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v :
          (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌) r)) = 0 := by
    rw [Finsupp.subtypeDomain_eq_zero_iff']
    intro x hpx
    by_cases hxv : x = (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v :
        (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌)
    · subst hxv; exact absurd hpx hGv
    · exact Finsupp.single_eq_of_ne hxv
  have hstep : (Finsupp.lmapDomain R R
      (fun v' : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
        (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v' :
          (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌))
      (Finsupp.single v r))
      = Finsupp.single (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v :
          (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌) r := by
    rw [Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
  conv_rhs => rw [hstep]
  rw [hL]
  exact (map_zero _).trans (((congrArg _ hR).trans (map_zero _)).symm)

/-- Two `R`-linear maps agreeing on the generators `single v 1` (`v ∈ S`) agree on any
element supported on `S`: rewrite `supported = span {single v 1}` and induct on the span,
using additivity/homogeneity of `F`, `G` for the closure steps. -/
theorem linear_eq_on_supported {ι κ : Type*} {R : Type} [Ring R]
    (S : Set ι) (F G : (ι →₀ R) →ₗ[R] (κ →₀ R))
    (hgen : ∀ v ∈ S, F (Finsupp.single v 1) = G (Finsupp.single v 1))
    (a : ι →₀ R) (ha : a ∈ Finsupp.supported R R S) :
    F a = G a  := by
  rw [Finsupp.supported_eq_span_single] at ha
  induction ha using Submodule.span_induction with
  | mem x hx =>
    obtain ⟨v, hv, rfl⟩ := hx
    exact hgen v hv
  | zero => simp
  | add x y _ _ hx hy => simp only [map_add, hx, hy]
  | smul r x _ hx => simp only [map_smul, hx]

/-- The succAbove vertex-pushforward `FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)`
carries the (n+1)-simplex into the (n+2)-simplex and reflects it, since `Fin.succAbove i`
is injective. Two ingredients: (1) the pushforward preserves the total sum
(`Finset.sum_fiberwise`, any map), so `∑ = 1` transfers both ways; (2) nonnegativity is
pointwise reflected because the fiber of an injective map over `succAbove i x` is `{x}`,
giving `w x = (pushforward w) (succAbove i x)`, while forward nonnegativity is a fiber sum
of nonnegatives. Unfold both `stdSimplex` memberships into their `(nonneg) ∧ (sum = 1)`
pairs and thread these two facts through each direction. -/
theorem pushforward_mem_stdsimplex_iff (n : ℕ) (i : Fin (n + 2))
    (w : Fin (n + 1) → ℝ) :
    FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i) w ∈ stdSimplex ℝ (Fin (n + 2))
      ↔ w ∈ stdSimplex ℝ (Fin (n + 1))  := by
  classical
  have hsum : ∑ y, FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i) w y = ∑ x, w x := by
    simp only [FunOnFinite.linearMap_apply_apply]
    exact Finset.sum_fiberwise Finset.univ _ w
  have hinj : Function.Injective (Fin.succAbove i) := Fin.succAbove_right_injective
  have hpt : ∀ x, w x = FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i) w (Fin.succAbove i x) := by
    intro x
    rw [FunOnFinite.linearMap_apply_apply]
    have hfil : (Finset.univ.filter (fun x' => Fin.succAbove i x' = Fin.succAbove i x)) = {x} := by
      ext x'; simp [hinj.eq_iff]
    rw [hfil, Finset.sum_singleton]
  constructor
  · rintro ⟨hn, hs⟩
    refine ⟨fun x => ?_, ?_⟩
    · rw [hpt x]; exact hn _
    · rw [← hsum]; exact hs
  · rintro ⟨hn, hs⟩
    refine ⟨fun y => ?_, ?_⟩
    · rw [FunOnFinite.linearMap_apply_apply]
      exact Finset.sum_nonneg (fun x _ => hn x)
    · rw [hsum]; exact hs

/-- Degree-`m` analogue of `succabove_pushforward_stdsimplex_iff` (there fixed at degree
`n`); identical proof, generic in `m`. Reduce `Set.range _ ⊆ _` to pointwise `∀ j`
membership via `Set.range_subset_iff`, then close by `forall_congr'` of the per-vertex
pushforward-membership iff `pushforward_mem_stdsimplex_iff`. -/
theorem range_pushforward_subset_stdsimplex_iff_deg (n : ℕ) (i : Fin (n + 2)) {m : ℕ}
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌) :
    Set.range (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v
        : (affine_sset (Fin (n + 2) → ℝ)) _⦋m⦌) ⊆ stdSimplex ℝ (Fin (n + 2))
      ↔ Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)) := by
  simp only [Set.range_subset_iff, Function.comp_apply]
  exact forall_congr' (fun j => pushforward_mem_stdsimplex_iff n i (v j))

/-- Range-support of the succAbove vertex-pushforward composite lies in the (n+2)-simplex
iff `v`'s range lies in the (n+1)-simplex. Reduce `Set.range _ ⊆ _` to a pointwise
`∀ j`-quantified membership (`Set.range_subset_iff`), then close by `forall_congr'` of
the per-vertex pushforward-membership iff `pushforward_mem_stdsimplex_iff`. -/
theorem succabove_pushforward_stdsimplex_iff (n : ℕ) (i : Fin (n + 2))
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) :
    Set.range (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v
        : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌) ⊆ stdSimplex ℝ (Fin (n + 2))
      ↔ Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)) :=
  range_pushforward_subset_stdsimplex_iff_deg n i v

/-- Degree-`m` analogue of `transport_face_generator`: face-transport on a single
generator `single v r` (`v` of arbitrary degree `m`), given directly that `v`'s
range lies in the standard simplex (rather than splitting on the support condition). -/
theorem transport_face_generator_deg {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) (i : Fin (n + 2)) {m : ℕ}
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌)
    (hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1))) (r : R) :
    Finsupp.lmapDomain R R
        ((singular_transport ((TopCat.toSSet.obj X).δ i σ)).app (Opposite.op ⦋m⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single v r))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋m⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋m⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (Finsupp.lmapDomain R R
              (fun v' : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ =>
                (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v' :
                  (affine_sset (Fin (n + 2) → ℝ)) _⦋m⦌))
              (Finsupp.single v r)))  := by
  classical
  have hGv : Set.range (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v
      : (affine_sset (Fin (n + 2) → ℝ)) _⦋m⦌) ⊆ stdSimplex ℝ (Fin (n + 2)) :=
    (range_pushforward_subset_stdsimplex_iff_deg n i v).mpr hv
  have hLHS : Finsupp.subtypeDomain
      (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ =>
        Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single v r)
      = Finsupp.single (⟨v, hv⟩ : {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ //
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))}) r := by
    ext ⟨a, ha⟩
    rw [Finsupp.subtypeDomain_apply]
    by_cases h : a = v
    · subst h
      erw [Finsupp.single_eq_same, Finsupp.single_eq_same]
    · erw [Finsupp.single_eq_of_ne h,
          Finsupp.single_eq_of_ne (fun heq => h (congrArg Subtype.val heq))]
  have hRHS : Finsupp.subtypeDomain
      (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋m⦌ =>
        Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
      (Finsupp.lmapDomain R R
          (fun v' : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ =>
            (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v' :
              (affine_sset (Fin (n + 2) → ℝ)) _⦋m⦌))
          (Finsupp.single v r))
      = Finsupp.single (⟨⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v, hGv⟩ :
          {w : (affine_sset (Fin (n + 2) → ℝ)) _⦋m⦌ //
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 2))}) r := by
    rw [Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
    ext ⟨a, ha⟩
    rw [Finsupp.subtypeDomain_apply]
    by_cases h : a = (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v)
    · subst h
      erw [Finsupp.single_eq_same, Finsupp.single_eq_same]
    · erw [Finsupp.single_eq_of_ne h,
          Finsupp.single_eq_of_ne (fun heq => h (congrArg Subtype.val heq))]
  rw [hLHS, hRHS]
  erw [Finsupp.lmapDomain_apply, Finsupp.lmapDomain_apply,
      Finsupp.mapDomain_single, Finsupp.mapDomain_single]
  rw [singular_transport_face σ i ⟨v, hv⟩ hGv]
  rfl

/-- Reduce both sides to a `single` at one point via `subtypeDomain`/`lmapDomain`
computation rules, then close with the proved geometric fact `singular_transport_face`.
Since `v`/`hv` satisfy the standard-simplex support condition (resp. the
pushed-forward `hGv`), `subtypeDomain (single v r) = single ⟨v, hv⟩ r` on each
side (proved pointwise via `single_eq_same`/`single_eq_of_ne`, using `erw`
since the coercions through the `SSet` object level are only semireducibly
defeq to plain function application). Pushing `single ⟨v, hv⟩ r` through the
`lmapDomain`s collapses both sides to `single (_ ⟨v, hv⟩) r`, and
`singular_transport_face` gives exactly the needed point equality;
the residual `↑⟨v, hv⟩` vs `v` gap is closed by `rfl` (definitional). -/
theorem transport_face_generator_pos {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) (i : Fin (n + 2))
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) (r : R)
    (hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)))
    (_hGv : Set.range (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v
        : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌) ⊆ stdSimplex ℝ (Fin (n + 2))) :
    Finsupp.lmapDomain R R
        ((singular_transport ((TopCat.toSSet.obj X).δ i σ)).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single v r))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (Finsupp.lmapDomain R R
              (fun v' : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v' :
                  (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌))
              (Finsupp.single v r))) := transport_face_generator_deg n σ i v hv r

/-- Face-transport on a single generator `single v r`, split by whether `v`'s vertices
lie in the standard simplex. `succabove_pushforward_stdsimplex_iff` bridges the
support condition through the vertex pushforward `FunOnFinite.linearMap succAbove`
(a face inclusion preserves/reflects stdSimplex-membership). The positive case
(`transport_face_generator_pos`) reduces both sides to a singleton and closes via
`singular_transport_face`; the negative case (`transport_face_generator_neg`) has
both `subtypeDomain`-of-`single` restrictions vanish, so both sides are `0`. -/
theorem transport_face_generator {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) (i : Fin (n + 2))
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) (r : R) :
    Finsupp.lmapDomain R R
        ((singular_transport ((TopCat.toSSet.obj X).δ i σ)).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single v r))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (Finsupp.lmapDomain R R
              (fun v' : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v' :
                  (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌))
              (Finsupp.single v r)))  := by
  classical
  by_cases hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1))
  · exact transport_face_generator_pos n σ i v r hv
      ((succabove_pushforward_stdsimplex_iff n i v).mpr hv)
  · exact transport_face_generator_neg n σ i v r hv
      (fun h => hv ((succabove_pushforward_stdsimplex_iff n i v).mp h))

/-- Degree-parametric face-compatibility of `singular_transport` on a supported affine
chain `a`. Both sides are `R`-linear in `a`, so it suffices to check the identity on
the generators `single v 1` of the supported submodule. `linear_eq_on_supported`
packages the span-of-single induction (both sides expressed as composites of
`Finsupp.lmapDomain` / `Finsupp.lsubtypeDomain` linear maps), and
`transport_face_generator_deg` supplies the single-generator case. -/
theorem transport_face_supported_deg {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) (i : Fin (n + 2)) {m : ℕ}
    (a : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ →₀ R)
    (ha : a ∈ Finsupp.supported R R
        {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ |
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))}) :
    Finsupp.lmapDomain R R
        ((singular_transport ((TopCat.toSSet.obj X).δ i σ)).app (Opposite.op ⦋m⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) a)
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋m⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋m⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (Finsupp.lmapDomain R R
              (fun v : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ =>
                (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v :
                  (affine_sset (Fin (n + 2) → ℝ)) _⦋m⦌))
              a))  := by
  exact linear_eq_on_supported
    {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ | Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))}
    (Finsupp.lmapDomain R R
        ((singular_transport ((TopCat.toSSet.obj X).δ i σ)).app (Opposite.op ⦋m⦌))
      ∘ₗ Finsupp.lsubtypeDomain
          {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ | Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))})
    (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋m⦌))
      ∘ₗ Finsupp.lsubtypeDomain
          {w : (affine_sset (Fin (n + 2) → ℝ)) _⦋m⦌ | Set.range w ⊆ stdSimplex ℝ (Fin (n + 2))}
      ∘ₗ Finsupp.lmapDomain R R
          (fun v : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ =>
            (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v :
              (affine_sset (Fin (n + 2) → ℝ)) _⦋m⦌)))
    (fun v hv => transport_face_generator_deg n σ i v hv 1) a ha

/-- Degree-`n` instance of `transport_face_supported_deg`: face-compatibility of
`singular_transport` on a supported affine chain `a` at the matching degree `n`. -/
theorem transport_face_on_supported_chain {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) (i : Fin (n + 2))
    (a : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R)
    (ha : a ∈ Finsupp.supported R R
        {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ |
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))}) :
    Finsupp.lmapDomain R R
        ((singular_transport ((TopCat.toSSet.obj X).δ i σ)).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) a)
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (Finsupp.lmapDomain R R
              (fun v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                (⇑(FunOnFinite.linearMap ℝ ℝ (Fin.succAbove i)) ∘ v :
                  (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌))
              a)) := transport_face_supported_deg n σ i a ha

/-- Face-transport of the singular subdivision on a boundary generator `δ i σ`.
Unfold `singular_sd` on the generator (`singular_sd_single_gen`), rewrite the
affine face-simplex chain as a vertex-pushforward of the fundamental subdivided
chain (`affine_sd_face_eq`, via `affine_sd` naturality), then transport the
singular realization across the face (`transport_face_on_supported_chain`, via
`singular_transport` face-compatibility on the std-simplex-supported chain
`affine_sd_single_tuple_supported`). -/
theorem singular_sd_single_face_transport {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) (i : Fin (n + 2)) :
    singular_sd (R := R) n (Finsupp.single ((TopCat.toSSet.obj X).δ i σ) 1)
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (affine_sd (R := R) n
              (Finsupp.single ((affine_sset (Fin (n + 2) → ℝ)).δ i
                  (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ))) 1)))  := by
  have h_gen := singular_sd_single_gen (R := R) n ((TopCat.toSSet.obj X).δ i σ)
  have h_affine := affine_sd_face_eq (R := R) n i
  have h_face := transport_face_on_supported_chain (R := R) n σ i
    (affine_sd (R := R) n (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1))
    (affine_sd_single_tuple_supported n)
  rw [h_gen, h_affine]
  exact h_face

/-- Chain-map identity `∂ ∘ S = S ∘ ∂` (rhs half) on the generator `single σ 1`,
factored through `singular_transport σ`. Expand both sides face-by-face over
`i : Fin (n+2)`: `singular_sd_lhs_face_sum` turns `S (∂σ)` into the alternating
sum of `S (single (δ i σ) 1)` (via `lmapdomain_sum_on_generator` + linearity of
`singular_sd`); `singular_sd_mid_face_sum` turns the transported affine boundary
into the matching alternating sum (affine `lmapdomain_sum_on_generator` +
linearity of `affine_sd`/`subtypeDomain`/`lmapDomain`); and per face
`singular_sd_single_face_transport` identifies the two summands (definition of
`singular_sd` + `singular_transport_face` + affine naturality `affine_sd_map`). -/
theorem singular_sd_boundary_transport_rhs {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    singular_sd (R := R) n
        ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
            • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
          (Finsupp.single σ 1))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (affine_sd (R := R) n
              ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
                  • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))  := by
  have h1 := singular_sd_lhs_face_sum (R := R) n σ
  have h2 := singular_sd_mid_face_sum (R := R) n σ
  rw [h1, h2]
  exact Finset.sum_congr rfl
    (fun i _ => by rw [singular_sd_single_face_transport (R := R) n σ i])

/-- Chain-map identity `∂ ∘ S = S ∘ ∂` for the singular subdivision on the generator
`single σ 1`, factored through the transport morphism `singular_transport σ`:
both sides equal the transported affine boundary of the subdivided fundamental
chain. `singular_sd_boundary_transport_lhs` pushes the singular boundary through
the transport (naturality of `singular_transport` + the affine chain-map
`affine_sd_boundary`); `singular_sd_boundary_transport_rhs` expands `S (∂ σ)`
face-by-face (`singular_transport_face` + affine naturality `affine_sd_map`), and
`Eq.trans`/`Eq.symm` glue the two directions through the common middle term. -/
theorem singular_sd_boundary_gen {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
        (singular_sd (R := R) (n + 1) (Finsupp.single σ 1))
      = singular_sd (R := R) n
          ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
            (Finsupp.single σ 1))  := by
  have h_lhs := singular_sd_boundary_transport_lhs (R := R) n σ
  have h_rhs := singular_sd_boundary_transport_rhs (R := R) n σ
  exact h_lhs.trans h_rhs.symm

/-- Reduce the map identity `∂ ∘ S = S ∘ ∂` (singular subdivision is a chain map) to a
single generator `single σ 1` via `Finsupp.lhom_ext'` + `LinearMap.ext_ring`; the
per-generator equation is deferred to `singular_sd_boundary_gen` (the transport
argument: naturality of `singular_transport` w.r.t. faces + the affine
`affine_sd_boundary` on the standard simplex). -/
theorem singular_sd_boundary {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ) :
    (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
        ∘ₗ singular_sd (R := R) (n + 1)
      = singular_sd (R := R) n
        ∘ₗ (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
            • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))  := by
  apply Finsupp.lhom_ext'
  intro σ
  apply LinearMap.ext_ring
  have hgen :
      (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
        (singular_sd (R := R) (n + 1) (Finsupp.single σ 1))
      = singular_sd (R := R) n
          ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
            (Finsupp.single σ 1)) := singular_sd_boundary_gen n σ
  simpa only [LinearMap.comp_apply, Finsupp.lsingle_apply] using hgen

/-- Face-compatibility of `singular_transport` on the specific supported affine
homotopy chain `affine_ht n (single fund 1)`: this is the degree-`(n+1)`,
specific-chain instance of the degree-parametric naturality
`transport_face_supported_deg`. Discharge the support side-condition with the
proved `affine_ht_single_tuple_supported`. -/
theorem singular_transport_face_lmapdomain {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) (i : Fin (n + 2)) :
    Finsupp.lmapDomain R R
        ((singular_transport ((TopCat.toSSet.obj X).δ i σ)).app (Opposite.op ⦋n + 1⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n + 1⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (affine_ht (R := R) n
            (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1)))
      = Finsupp.lmapDomain R R
        ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
          (Finsupp.lmapDomain R R
            (fun v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n + 1⦌ =>
              (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘ v
                : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌))
            (affine_ht (R := R) n
              (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1)))) :=
  transport_face_supported_deg n σ i
    (affine_ht (R := R) n (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1))
    (affine_ht_single_tuple_supported n)

/-- Face-compatibility of the singular chain homotopy `T = singular_ht` on a single
face generator: unfold `singular_ht` at `single (δ i σ) 1` (via
`Finsupp.linearCombination_single`) to the transport of the fundamental affine
homotopy, then match the RHS through two independent naturalities.
* `affine_ht_single_face_pushforward` (`h1`): the affine face `δ i` of the fundamental
  tuple, hit by `affine_ht n`, equals the vertex-pushforward
  (`FunOnFinite.linearMap i.succAbove`) of `affine_ht n` on the smaller fundamental
  tuple — affine naturality of `affine_ht` under the linear vertex map.
* `singular_transport_face_lmapdomain` (`h2`): pushing the supported affine homotopy
  chain forward along `singular_transport (δ i σ)` equals pushing its vertex-image
  forward along `singular_transport σ` — the chain-level face-compatibility of
  `singular_transport`. `rw [h2, h1]` then closes the goal. -/
theorem singular_ht_single_face_transport {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) (i : Fin (n + 2)) :
    @singular_ht R _ X n (Finsupp.single ((TopCat.toSSet.obj X).δ i σ) 1)
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (affine_ht (R := R) n
              (Finsupp.single ((affine_sset (Fin (n + 2) → ℝ)).δ i
                  (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ))) 1)))  := by
  simp only [singular_ht, singular_ht, Finsupp.linearCombination_single, one_smul]
  have h1 : affine_ht (R := R) n
        (Finsupp.single ((affine_sset (Fin (n + 2) → ℝ)).δ i
            (fun j => (Pi.single j 1 : Fin (n + 2) → ℝ))) 1)
      = Finsupp.lmapDomain R R
          (fun v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n + 1⦌ =>
            (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘ v
              : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌))
          (affine_ht (R := R) n
            (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1)) :=
    affine_ht_single_face_pushforward n i
  have h2 : Finsupp.lmapDomain R R
        ((singular_transport ((TopCat.toSSet.obj X).δ i σ)).app (Opposite.op ⦋n + 1⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n + 1⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (affine_ht (R := R) n
            (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1)))
      = Finsupp.lmapDomain R R
        ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
          (Finsupp.lmapDomain R R
            (fun v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n + 1⦌ =>
              (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘ v
                : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌))
            (affine_ht (R := R) n
              (Finsupp.single (fun j => (Pi.single j 1 : Fin (n + 1) → ℝ)) 1)))) :=
    singular_transport_face_lmapdomain n σ i
  rw [h2, h1]

/-- Transport the `T∂`-side of Hatcher's `∂T + T∂ = id − S` from singular to affine.
Expand the singular boundary + `T`-linearity (`singular_ht_lhs_face_sum`), match the
pushed affine boundary sum (`singular_ht_mid_face_sum`), then identify each face term
via face-compatibility of `singular_transport` (`singular_ht_single_face_transport`). -/
theorem singular_ht_boundary_td_term {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    @singular_ht R _ X n
        ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) (Finsupp.single σ 1))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (affine_ht (R := R) n
              ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
                  • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))  := by
  rw [singular_ht_lhs_face_sum, singular_ht_mid_face_sum]
  refine Finset.sum_congr rfl fun i _ => ?_
  rw [singular_ht_single_face_transport n σ i]

/-- Per-generator singular chain-homotopy identity `∂T + T∂ = id − S` on `single σ 1`:
transport the proved affine identity `affine_ht_boundary` along `singular_transport σ`.
The two singular boundary terms are pushed to the affine level:
* `h_dt` (∂T side): simplicial naturality of `singular_transport σ` moves `∂` inside the
  pushforward, giving the affine `∂ ∘ affine_ht (n+1)` on the fundamental tuple;
* `h_td` (T∂ side): `singular_transport_face` rewrites `T (δ i σ)` as the pushforward of
  `affine_ht n` of the affine face `∂` of the fundamental tuple.

`h_combine` folds the two pushforwards (additivity of `lmapDomain`/`subtypeDomain`) and
applies `affine_ht_boundary` to collapse `∂ affine_ht + affine_ht ∂` to `id − affine_sd`.
`h_rhs` identifies the transported `id − affine_sd` on the fundamental tuple with
`single σ 1 − S (single σ 1)` via `singular_transport_fund` and the definition of `singular_sd`. -/
theorem singular_ht_boundary_on_generator {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌) :
    (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
        (@singular_ht R _ X (n + 1) (Finsupp.single σ 1))
      + @singular_ht R _ X n
        ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) (Finsupp.single σ 1))
      = Finsupp.single σ 1 - @singular_sd R _ X (n + 1) (Finsupp.single σ 1)  := by
  have h_dt :
      (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
          (@singular_ht R _ X (n + 1) (Finsupp.single σ 1))
        = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
              ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ)
                  • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
                (affine_ht (R := R) (n + 1)
                  (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1)))) :=
    singular_ht_boundary_dt_term (R := R) n σ
  have h_td :
      @singular_ht R _ X n
          ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
                • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) (Finsupp.single σ 1))
        = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
              (affine_ht (R := R) n
                ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
                    • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
                  (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1)))) :=
    singular_ht_boundary_td_term (R := R) n σ
  have h_combine :
      Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ)
                • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
              (affine_ht (R := R) (n + 1)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))
        + Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            (affine_ht (R := R) n
              ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
                  • Finsupp.lmapDomain R R ((affine_sset (Fin (n + 2) → ℝ)).δ i))
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))))
        = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            ((Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1
                  : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ →₀ R)
              - affine_sd (R := R) (n + 1)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1))) :=
    singular_ht_boundary_affine_combine (R := R) n σ
  have h_rhs :
      Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 2)))
            ((Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1
                  : (affine_sset (Fin (n + 2) → ℝ)) _⦋n + 1⦌ →₀ R)
              - affine_sd (R := R) (n + 1)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 2) → ℝ)) 1)))
        = Finsupp.single σ 1 - @singular_sd R _ X (n + 1) (Finsupp.single σ 1) :=
    singular_ht_boundary_transport_rhs (R := R) n σ
  rw [h_dt, h_td, h_combine]; exact h_rhs

/-- Singular chain-homotopy identity `∂T + T∂ = id − S`, the singular transport of the
proved affine `affine_ht_boundary`. Reduce the endomorphism equality to a per-generator
identity via `Finsupp.lhom_ext'` + `LinearMap.ext_ring`, then discharge each generator `σ`
by `singular_ht_boundary_on_generator` (where the transport of the affine identity along
`singular_transport σ` — face-compatibility + fundamental round-trip — is carried out). -/
theorem singular_ht_boundary {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ) :
    (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
        ∘ₗ (@singular_ht R _ X (n + 1))
      + (@singular_ht R _ X n)
        ∘ₗ (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
      = LinearMap.id - (@singular_sd R _ X (n + 1))  := by
  apply Finsupp.lhom_ext'
  intro σ
  apply LinearMap.ext_ring
  have h_gen := singular_ht_boundary_on_generator (R := R) (X := X) n σ
  simpa only [LinearMap.comp_apply, LinearMap.add_apply, LinearMap.sub_apply,
    LinearMap.id_apply, Finsupp.lsingle_apply] using h_gen

/-- The range of the transported simplex lands inside the range of `σ`: pointwise,
`singular_transport_app_eval` rewrites each value to `(toSSetObjEquiv σ) ⟨...⟩`,
which is manifestly in `Set.range (toSSetObjEquiv σ)`. -/
theorem singular_transport_range
    {X : TopCat.{0}} {n : ℕ} (σ : (TopCat.toSSet.obj X) _⦋n⦌) {m : ℕ}
    (w : {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ //
        Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))}) :
    Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋m⦌)
        ((singular_transport σ).app (Opposite.op ⦋m⦌) w)) ⊆
      Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ)  := by
  rw [Set.range_subset_iff]
  intro z
  rw [singular_transport_app_eval σ w z]
  exact Set.mem_range_self _

end Library.AlgebraicTopology.MayerVietoris.SingularSubdivisionHomotopy
