import Mathlib.Algebra.Category.ModuleCat.Biproducts
import Mathlib.Algebra.Category.ModuleCat.Products
import Mathlib.Algebra.Homology.HomologicalComplexAbelian
import Mathlib.Algebra.Homology.HomologicalComplexBiprod
import Mathlib.Algebra.Lie.OfAssociative
import Mathlib.AlgebraicTopology.SimplicialSet.Homology.Basic
import Mathlib.AlgebraicTopology.SingularSet
import Mathlib.Analysis.Normed.Group.AddTorsor
import Mathlib.Analysis.Normed.Module.Convex
import Mathlib.Analysis.RCLike.Basic
import Mathlib.Combinatorics.Quiver.ReflQuiver

/-!
# The Mayer–Vietoris short exact sequence of chain complexes

This file constructs, for a subcomplex pair `A B` of a simplicial set `X`, the short exact
sequence of chain complexes

`0 → C(A ⊓ B) → C(A) ⊞ C(B) → C(A ⊔ B) → 0`

underlying the Mayer–Vietoris long exact sequence in (co)homology, where `C(A)` denotes the
sub-chain-complex of chains supported on `A` (identified with `Finsupp.supported R R (A.obj _)`
in each degree via the degreewise iso `chain_complex_x_iso_finsupp`).

The argument has two independent halves, glued degreewise:

* An algebraic pillar (`submodule_inf_prod_sup_short_exact`): for a pair of submodules `p q` of an
  `R`-module `M`, `0 → p ⊓ q → p × q → p ⊔ q → 0` is short exact, via the maps
  `x ↦ (x, -x)` and `(a, b) ↦ a + b`.
* A comparison isomorphism (`mv_map_eval_iso_algebraic`) identifying, at each simplicial degree,
  the algebraic short complex on the underlying `Finsupp` submodules with the categorical
  `mv_short_complex` built from `supported_chain_complex_incl`.

The file also develops the affine (linear-combination) model of chains on a normed space `E`
(`affine_sset`, `affine_cone`, `affine_sd`) used elsewhere for the barycentric subdivision
operator and its associated chain homotopy (Hatcher §2.1), together with the centroid distance
estimates (`centroid_dist_le_diam_mul`) that drive the mesh-shrinking argument for subdivided
simplices.

## Main definitions

* `singular_subcomplex_of_set`: the subcomplex of singular simplices of `X` supported in `U`.
* `chain_complex_x_iso_finsupp`: the degreewise identification of `X.chainComplex R` with the
  free module on `X`'s simplices.
* `affine_sset`: the simplicial set of affine chains on `E`, with `n`-simplices vertex tuples.
* `affine_cone`: the cone operator `b · (-)` prepending an apex vertex to an affine simplex.
* `affine_sd`: the barycentric subdivision operator on affine chains.
* `supported_chain_complex`, `supported_chain_complex_incl`: the sub-chain-complex of chains
  supported on a subcomplex, and its inclusion for an inequality of subcomplexes.
* `mv_short_complex`: the Mayer–Vietoris short complex `0 → C(A ⊓ B) → C(A) ⊞ C(B) → C(A ⊔ B) → 0`.

## Main statements

* `mv_short_complex_short_exact`: the **Mayer–Vietoris short exact sequence** — `mv_short_complex`
  is short exact.
* `mv_short_complex_degreewise_short_exact`: its degreewise instance.
* `submodule_inf_prod_sup_short_exact`: the underlying algebraic short exact sequence of
  submodules.
* `affine_cone_boundary`, `affine_cone_zero_boundary`: the cone boundary identity
  `∂ ∘ cone b = id − cone b ∘ ∂`.
* `finsupp_boundary_sq_zero`: `∂ ∘ ∂ = 0` for the alternating-sum boundary.
-/

universe u

open CategoryTheory
open CategoryTheory CategoryTheory.Limits
open CategoryTheory Limits SSet Simplicial
open CategoryTheory Limits Simplicial
open CategoryTheory Simplicial
open Simplicial

namespace Library.AlgebraicTopology.MayerVietoris.ShortExactComplex

/-- The subcomplex of `TopCat.toSSet.obj X` of singular simplices supported in `U`: an
`n`-simplex (a continuous map from the standard simplex, via `toSSetObjEquiv`) qualifies iff its
range lies in `U`. Closure under `.map i` holds because `.map i` precomposes with
`stdSimplex.map i.unop`, which cannot enlarge the range. -/
noncomputable def singular_subcomplex_of_set (X : TopCat.{u}) (U : Set X) :
    (TopCat.toSSet.obj X).Subcomplex where
  obj n := { σ | Set.range ⇑(X.toSSetObjEquiv n σ) ⊆ U }
  map := by
    intro n m i x hx
    simp only [Set.mem_setOf_eq, Set.range_subset_iff] at hx ⊢
    intro z
    exact hx _

/-- A per-vertex distance bound extends to the whole convex hull of the vertices, via
`convexHull_min` into the convex set `Metric.closedBall c M`. -/
theorem dist_le_of_forall_vertex {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    (n : ℕ) (v : Fin (n + 1) → E) (c : E) (M : ℝ)
    (hv : ∀ j : Fin (n + 1), dist c (v j) ≤ M)
    {x : E} (hx : x ∈ convexHull ℝ (Set.range v)) :
    dist c x ≤ M := by
  have hsub : Set.range v ⊆ Metric.closedBall c M := by
    rintro y ⟨j, rfl⟩
    simpa [Metric.mem_closedBall, dist_comm] using hv j
  have := convexHull_min hsub (convex_closedBall c M) hx
  simpa [Metric.mem_closedBall, dist_comm] using this

/-- Injective since the first component `Submodule.inclusion` is already injective, independent
of the sign on the second component. -/
theorem inf_prod_neg_injective
    {R : Type*} [Ring R] {M : Type*} [AddCommGroup M] [Module R M]
    (p q : Submodule R M) :
    Function.Injective (LinearMap.prod (Submodule.inclusion (inf_le_left : p ⊓ q ≤ p))
      (-Submodule.inclusion (inf_le_right : p ⊓ q ≤ q))) := by
  intro x y h
  simp only [LinearMap.prod_apply, Pi.prod, Prod.mk.injEq] at h
  exact Submodule.inclusion_injective (inf_le_left : p ⊓ q ≤ p) h.1

/-- Exactness of the Mayer–Vietoris algebraic short exact sequence at the middle term:
`range f = ker g`, where `f = ⟨incl, -incl⟩ : p ⊓ q → p × q` and
`g = coprod incl incl : p × q → p ⊔ q`. Direct `le_antisymm` on submodules of the product: for
`⊆`, `f x = (x, -x)` lands in `ker g` since `(x : M) + (-(x : M)) = 0` in `p ⊔ q`; for `⊇`,
`(a, b) ∈ ker g` gives `(a : M) + (b : M) = 0`, so `(a : M) = -(b : M) ∈ q ∩ p`, and the witness
`⟨(a : M), _⟩ ∈ p ⊓ q` maps to `(a, b)` under `f`. -/
theorem inf_prod_range_eq_sup_ker
    {R : Type*} [Ring R] {M : Type*} [AddCommGroup M] [Module R M]
    (p q : Submodule R M) :
    LinearMap.range (LinearMap.prod (Submodule.inclusion (inf_le_left : p ⊓ q ≤ p))
      (-Submodule.inclusion (inf_le_right : p ⊓ q ≤ q)))
      = LinearMap.ker (LinearMap.coprod (Submodule.inclusion (le_sup_left : p ≤ p ⊔ q))
      (Submodule.inclusion (le_sup_right : q ≤ p ⊔ q))) := by
  apply le_antisymm
  · rintro _ ⟨x, rfl⟩
    rw [LinearMap.mem_ker]
    apply Subtype.ext
    simp [Submodule.coe_inclusion]
  · rintro ⟨a, b⟩ hab
    rw [LinearMap.mem_ker, Subtype.ext_iff] at hab
    simp only [LinearMap.coprod_apply, Submodule.coe_zero] at hab
    have h : (a:M) = -(b:M) := by rw [eq_neg_iff_add_eq_zero]; exact hab
    have haM : (a:M) ∈ p ⊓ q := ⟨a.2, h ▸ q.neg_mem b.2⟩
    refine ⟨⟨(a:M), haM⟩, ?_⟩
    apply Prod.ext
    · apply Subtype.ext; simp [Submodule.coe_inclusion]
    · apply Subtype.ext; simp [Submodule.coe_inclusion, h]

/-- `coprod (inclusion p ≤ p ⊔ q) (inclusion q ≤ p ⊔ q)` is surjective onto `↥(p ⊔ q)`. Any
`x ∈ p ⊔ q` splits as `y + z` with `y ∈ p`, `z ∈ q` (`Submodule.mem_sup`); the preimage
`(⟨y, hy⟩, ⟨z, hz⟩)` maps to `y + z = ↑x` (`coprod` of inclusions is addition of the underlying
carriers), so `Subtype.ext hyz` closes it. -/
theorem sup_coprod_surjective
    {R : Type*} [Ring R] {M : Type*} [AddCommGroup M] [Module R M]
    (p q : Submodule R M) :
    Function.Surjective (LinearMap.coprod (Submodule.inclusion (le_sup_left : p ≤ p ⊔ q))
      (Submodule.inclusion (le_sup_right : q ≤ p ⊔ q))) := by
  intro x
  obtain ⟨y, hy, z, hz, hyz⟩ := Submodule.mem_sup.mp x.2
  exact ⟨(⟨y, hy⟩, ⟨z, hz⟩), Subtype.ext hyz⟩

/-- The algebraic pillar of Mayer–Vietoris: `0 → p ⊓ q → p × q → p ⊔ q → 0` is short exact in
`ModuleCat R`. Splits `ShortExact` into its three fields via `mk'`, each reduced to a
`LinearMap`-level fact by the `ModuleCat` characterizations: exactness from `range f = ker g`
(`inf_prod_range_eq_sup_ker`), `mono_f` from `Injective f` (`inf_prod_neg_injective`), and `epi_g`
from `Surjective g` (`sup_coprod_surjective`). -/
theorem submodule_inf_prod_sup_short_exact
    {R : Type*} [Ring R] {M : Type*} [AddCommGroup M] [Module R M]
    (p q : Submodule R M) :
    (ShortComplex.moduleCatMk
      (LinearMap.prod (Submodule.inclusion (inf_le_left : p ⊓ q ≤ p))
        (-Submodule.inclusion (inf_le_right : p ⊓ q ≤ q)))
      (LinearMap.coprod (Submodule.inclusion (le_sup_left : p ≤ p ⊔ q))
        (Submodule.inclusion (le_sup_right : q ≤ p ⊔ q)))
      (by ext x; simp [Submodule.coe_inclusion])).ShortExact := by
  have h_mono := inf_prod_neg_injective p q
  have h_epi := sup_coprod_surjective p q
  have h_exact := inf_prod_range_eq_sup_ker p q
  apply ShortComplex.ShortExact.mk'
  · rw [ShortComplex.moduleCat_exact_iff_range_eq_ker]; exact h_exact
  · rw [ModuleCat.mono_iff_injective]; exact h_mono
  · rw [ModuleCat.epi_iff_surjective]; exact h_epi

/-- Centroid algebra: `dist(centroid, v j) = (n + 1)⁻¹ · ‖∑ i, (v i - v j)‖`. Rewrites `dist` to a
norm, expresses `centroid - v j = (n + 1)⁻¹ • ∑ (v i - v j)` via `Finset.centroid_def` +
`Finset.affineCombination_eq_linear_combination` (centroid weights are `(n + 1)⁻¹`), then closes
with `norm_smul` and `‖(n + 1)⁻¹‖ = (n + 1)⁻¹` (nonneg). -/
theorem centroid_sub_vertex_norm {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    (n : ℕ) (v : Fin (n + 1) → E) (j : Fin (n + 1)) :
    dist (Finset.univ.centroid ℝ v) (v j)
      = ((n : ℝ) + 1)⁻¹ * ‖∑ i, (v i - v j)‖ := by
  rw [dist_eq_norm]
  have hc : Finset.univ.centroid ℝ v - v j
      = ((n : ℝ) + 1)⁻¹ • ∑ i, (v i - v j) := by
    rw [Finset.centroid_def, Finset.affineCombination_eq_linear_combination _ _ _
      (Finset.sum_centroidWeights_eq_one_of_nonempty ℝ _ (by simp))]
    simp only [Finset.centroidWeights_apply, Finset.card_univ, Fintype.card_fin, Nat.cast_add,
      Nat.cast_one, smul_sub, Finset.sum_sub_distrib, Finset.smul_sum, Finset.sum_const,
      Finset.card_univ]
    have hn : (n : ℝ) + 1 ≠ 0 := by positivity
    rw [← Nat.cast_smul_eq_nsmul ℝ (n + 1) (v j)]
    push_cast
    match_scalars <;> field_simp
  rw [hc, norm_smul]
  rw [Real.norm_eq_abs, abs_of_nonneg (by positivity)]

/-- The sum `∑ i, (v i - v j)` over all `n + 1` vertices is bounded by `n · diam(hull)`: dropping
the vanishing `i = j` term leaves `n` summands, each of norm at most the diameter of the convex
hull of `{v i}` by the triangle inequality. -/
theorem sum_vertex_diff_norm_le {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    (n : ℕ) (v : Fin (n + 1) → E) (j : Fin (n + 1)) :
    ‖∑ i, (v i - v j)‖
      ≤ (n : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) := by
  have hbd : Bornology.IsBounded (convexHull ℝ (Set.range v)) :=
    isBounded_convexHull.mpr (Set.finite_range v).isBounded
  have hsub : Set.range v ⊆ convexHull ℝ (Set.range v) := subset_convexHull ℝ _
  have hper : ∀ i, ‖v i - v j‖ ≤ Metric.diam (convexHull ℝ (Set.range v)) := by
    intro i
    rw [← dist_eq_norm]
    exact Metric.dist_le_diam_of_mem hbd (hsub ⟨i, rfl⟩) (hsub ⟨j, rfl⟩)
  calc ‖∑ i, (v i - v j)‖
      = ‖∑ i ∈ Finset.univ.erase j, (v i - v j)‖ := by
        rw [Finset.sum_erase]; simp
    _ ≤ ∑ i ∈ Finset.univ.erase j, ‖v i - v j‖ := norm_sum_le _ _
    _ ≤ ∑ i ∈ Finset.univ.erase j, Metric.diam (convexHull ℝ (Set.range v)) :=
        Finset.sum_le_sum (fun i _ => hper i)
    _ = (Finset.univ.erase j).card • Metric.diam (convexHull ℝ (Set.range v)) := by
        rw [Finset.sum_const]
    _ = (n : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) := by
        rw [Finset.card_erase_of_mem (Finset.mem_univ j), Finset.card_univ, Fintype.card_fin]
        simp [nsmul_eq_mul]

/-- For each vertex, `dist(centroid, v j) ≤ n / (n + 1) · diam(hull)`. Combines
`centroid_sub_vertex_norm` (`dist = (n + 1)⁻¹ · ‖∑ i, (v i - v j)‖`, centroid algebra) with
`sum_vertex_diff_norm_le` (`‖∑ i, (v i - v j)‖ ≤ n · diam`, triangle inequality on `n` nonzero
terms each bounded by `diam`), then closes with `gcongr` and `ring`. -/
theorem centroid_vertex_bound {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    (n : ℕ) (v : Fin (n + 1) → E) :
    ∀ j : Fin (n + 1),
      dist (Finset.univ.centroid ℝ v) (v j)
        ≤ (n / (n + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) := by
  intro j
  have hA : dist (Finset.univ.centroid ℝ v) (v j)
      = ((n : ℝ) + 1)⁻¹ * ‖∑ i, (v i - v j)‖ := centroid_sub_vertex_norm n v j
  have hB : ‖∑ i, (v i - v j)‖
      ≤ (n : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) := sum_vertex_diff_norm_le n v j
  calc dist (Finset.univ.centroid ℝ v) (v j)
        = ((n : ℝ) + 1)⁻¹ * ‖∑ i, (v i - v j)‖ := hA
      _ ≤ ((n : ℝ) + 1)⁻¹ * ((n : ℝ) * Metric.diam (convexHull ℝ (Set.range v))) := by gcongr
      _ = ((n : ℝ) / ((n : ℝ) + 1)) * Metric.diam (convexHull ℝ (Set.range v)) := by ring

/-- Bounds `dist(centroid, x)` for `x` in the vertex hull by `n / (n + 1) · diam`. The sharp bound
holds at each vertex `v j` (`centroid_vertex_bound`), and `dist(centroid, ·) ≤ M` on vertices lifts
to the whole convex hull via `dist_le_of_forall_vertex` (`closedBall` is convex and contains
`range v`, hence its hull). -/
theorem centroid_dist_le_diam_mul {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    (n : ℕ) (v : Fin (n + 1) → E) {x : E} (hx : x ∈ convexHull ℝ (Set.range v)) :
    dist (Finset.univ.centroid ℝ v) x
      ≤ (n / (n + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) := by
  set M : ℝ := (n / (n + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) with hM
  have hvert : ∀ j : Fin (n + 1), dist (Finset.univ.centroid ℝ v) (v j) ≤ M :=
    centroid_vertex_bound n v
  exact dist_le_of_forall_vertex n v (Finset.univ.centroid ℝ v) M hvert hx

/-- The vehicle that realizes a vertex tuple `v : Fin (n + 1) → E` as a singular simplex, i.e. the
continuous barycentric-combination map out of the topological standard simplex
`stdSimplex ℝ (Fin (n + 1))`, `x ↦ ∑ i, x i • v i`. This is the affine building block on which the
barycentric subdivision operator `S` and the chain homotopy `T` (Hatcher §2.1) are defined before
transport by naturality; feeds `centroid_dist_le_diam_mul` (via range ⊆ convexHull) for the
mesh-shrinking bound. -/
noncomputable def affine_simplex_map {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {n : ℕ} (v : Fin (n + 1) → E) : C(stdSimplex ℝ (Fin (n + 1)), E) :=
  ⟨fun x => ∑ i, (x : Fin (n + 1) → ℝ) i • v i, by
    refine continuous_finsetSum _ fun i _ => ?_
    exact (((continuous_apply i).comp continuous_subtype_val).smul continuous_const)⟩

/-- Degreewise identification of the simplicial chain module with a free module.
`(X.chainComplex R).X n` is by construction the coproduct `∐_{x : X_⦋n⦌} R`; transports it along
the canonical colimit iso to `∐`, then `coprodIsoDirectSum` to `DirectSum (X _⦋n⦌) (fun _ ↦ R) =
Π₀`, then `finsuppLequivDFinsupp` back to the finitely-supported functions `X _⦋n⦌ →₀ R`. -/
noncomputable def chain_complex_x_iso_finsupp
    {R : Type u} [Ring R] (X : SSet.{u}) (n : ℕ) :
    (X.chainComplex (ModuleCat.of R R)).X n ≅ ModuleCat.of R (X _⦋n⦌ →₀ R) := by
  classical
  exact (X.isColimitChainComplexXCofan (ModuleCat.of R R) n).coconePointUniqueUpToIso
      (colimit.isColimit _)
    ≪≫ ModuleCat.coprodIsoDirectSum (fun (_ : X _⦋n⦌) ↦ ModuleCat.of R R)
    ≪≫ (finsuppLequivDFinsupp R (M := R)).symm.toModuleIso

/-- `chain_complex_x_iso_finsupp` sends the generator `ιChainComplex σ` to `Finsupp.single σ`.
Unfolds the three-step iso: `coconePointUniqueUpToIso` carries the cofan injection
`ιChainComplex σ` to the coproduct injection `Sigma.ι`; `ι_coprodIsoDirectSum_hom` turns that into
`DirectSum.lof … σ`; and `finsuppLequivDFinsupp.symm = DFinsupp.toFinsupp` sends `single σ` to
`Finsupp.single σ`, closing on generators. -/
theorem chain_complex_x_iso_finsupp_single
    {R : Type u} [Ring R] (X : SSet.{u}) (n : ℕ) (σ : X _⦋n⦌) :
    X.ιChainComplex σ ≫ (chain_complex_x_iso_finsupp (R := R) X n).hom
      = ModuleCat.ofHom (Finsupp.lsingle σ) := by
  classical
  simp only [chain_complex_x_iso_finsupp, Iso.trans_hom]
  have h1 : X.ιChainComplex σ ≫
        ((X.isColimitChainComplexXCofan (ModuleCat.of R R) n).coconePointUniqueUpToIso
        (colimit.isColimit (Discrete.functor fun _ ↦ ModuleCat.of R R))).hom
      = Sigma.ι (fun (_ : X _⦋n⦌) ↦ ModuleCat.of R R) σ :=
    (X.isColimitChainComplexXCofan (ModuleCat.of R R) n).comp_coconePointUniqueUpToIso_hom
      (colimit.isColimit _) ⟨σ⟩
  rw [← Category.assoc, h1, ← Category.assoc]
  erw [ModuleCat.ι_coprodIsoDirectSum_hom]
  rw [LinearEquiv.toModuleIso_hom]
  apply ModuleCat.hom_ext
  refine LinearMap.ext fun r ↦ ?_
  simp only [ModuleCat.hom_comp, ModuleCat.hom_ofHom, LinearMap.comp_apply,
    Finsupp.lsingle_apply]
  erw [ModuleCat.hom_ofHom]
  change DFinsupp.toFinsupp (DFinsupp.single σ r) = _
  exact DFinsupp.toFinsupp_single σ r

/-- `stdSimplex.map f x` pushes barycentric weights forward along `f`; the weighted sum against
`v` over `Y` regroups into a weighted sum against `v ∘ f` over `X`. Expands `map` via
`stdSimplex.map_coe` + `FunOnFinite.linearMap_apply_apply` (each pushed weight is the fiber sum of
source weights), folds the `Y`-sum back through the fibers with `Finset.sum_fiberwise`, distributes
`Finset.sum_smul`, and rewrites `v y = v (f i)` using the fiber membership `f i = y`. -/
theorem std_simplex_map_weighted_sum {E : Type*} [AddCommMonoid E] [Module ℝ E]
    {X Y : Type*} [Fintype X] [Fintype Y]
    (f : X → Y) (x : stdSimplex ℝ X) (v : Y → E) :
    ∑ y, (stdSimplex.map f x : Y → ℝ) y • v y
      = ∑ i, (x : X → ℝ) i • v (f i) := by
  classical
  simp only [stdSimplex.map_coe, FunOnFinite.linearMap_apply_apply]
  rw [← Finset.sum_fiberwise Finset.univ f (fun i => (x : X → ℝ) i • v (f i))]
  refine Finset.sum_congr rfl (fun y _ => ?_)
  rw [Finset.sum_smul]
  refine Finset.sum_congr rfl (fun i hi => ?_)
  rw [Finset.mem_filter] at hi
  rw [hi.2]

/-- The simplicial set of affine chains on `E`: its `n`-simplices are vertex tuples
`Fin (n + 1) → E`, with simplicial action by precomposition `map f v = v ∘ f.unop.toOrderHom` (so
faces are vertex deletion via `Fin.succAbove`, and `map_id`/`map_comp` hold by the functor
defaults). This is the `SSet`-level home for Hatcher's LC affine chains: `(affine_sset
E).chainComplex R` then inherits `∂² = 0` and the full generator API (`SSet.ιChainComplex`, …) for
free, and it composes with `TopCat.toSSet` for the realization comparison chain map. -/
def affine_sset (E : Type u) : SSet.{u} where
  obj m := Fin (m.unop.len + 1) → E
  map f := TypeCat.ofHom (fun v => v ∘ f.unop.toOrderHom)

/-- The range of the affine realization `x ↦ ∑ i, x i • v i` lands in `convexHull ℝ (range v)`.
A point `x` of the standard simplex has nonnegative coordinates summing to `1`, so the image is a
convex combination of the `v i`; closes via `Convex.sum_mem` on `convex_convexHull`, with each
`v i ∈ convexHull` by `subset_convexHull`. -/
theorem affine_simplex_map_range_subset_convexHull {E : Type*} [NormedAddCommGroup E]
    [NormedSpace ℝ E] {n : ℕ} (v : Fin (n + 1) → E) :
    Set.range ⇑(affine_simplex_map v) ⊆ convexHull ℝ (Set.range v) := by
  rintro y ⟨x, rfl⟩
  refine Convex.sum_mem (convex_convexHull ℝ _) (fun i _ => x.2.1 i) x.2.2 ?_
  intro i _
  exact subset_convexHull ℝ _ (Set.mem_range_self i)

/-- Face maps preserve subcomplex membership, via `Subfunctor.map`: `X.δ i = X.map
(SimplexCategory.δ i).op`, and `A.map` is exactly the preimage-closure field of `Subfunctor`, so
`Set.image_subset_iff` turns the image-subset goal into that field. -/
theorem subcomplex_face_image_subset
    (X : SSet.{u}) (A : X.Subcomplex) (n : ℕ) :
    ∀ (i : Fin (n + 2)),
      (X.δ i) '' (A.obj (Opposite.op ⦋n + 1⦌)) ⊆ A.obj (Opposite.op ⦋n⦌) := by
  intro i
  rw [Set.image_subset_iff]
  exact A.map (SimplexCategory.δ i).op

/-- The alternating sum of `lmapDomain (X.δ i)` composed with `lsingle σ` equals the alternating
sum of `lsingle (X.δ i σ)`. Follows by extensionality on the ring element `r`, then
`Finsupp.mapDomain_single` computes `mapDomain f (single σ r) = single (f σ) r` pointwise for each
summand. -/
theorem lmapdomain_sum_on_generator
    {R : Type u} [Ring R] (X : SSet.{u}) (n : ℕ) (σ : X _⦋n + 1⦌) :
    (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R (X.δ i)).comp
        (Finsupp.lsingle σ)
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lsingle ((X.δ i) σ) := by
  apply LinearMap.ext
  intro r
  simp only [LinearMap.comp_apply, LinearMap.sum_apply, LinearMap.smul_apply,
    Finsupp.lmapDomain_apply, Finsupp.lsingle_apply, Finsupp.mapDomain_single]

/-- The transported differential evaluated on a generator `lsingle σ`. Works at the `ModuleCat`
level: rewrites `ofHom (lsingle σ)` back into `ιChainComplex σ ≫ (chain_complex_x_iso_finsupp X
(n + 1)).hom` (`chain_complex_x_iso_finsupp_single`), cancels the iso `hom ≫ inv`
(`Iso.hom_inv_id_assoc`), applies `ιChainComplex_d` to expand the differential into
`∑ (-1) ^ i • ιChainComplex (X.δ i σ)`, distributes the trailing
`≫ (chain_complex_x_iso_finsupp X n).hom` over the sum, and sends each generator back through
`chain_complex_x_iso_finsupp_single`. -/
theorem transported_differential_on_generator
    {R : Type u} [Ring R] (X : SSet.{u}) (n : ℕ) (σ : X _⦋n + 1⦌) :
    (((chain_complex_x_iso_finsupp (R := R) X (n + 1)).inv
        ≫ (X.chainComplex (ModuleCat.of R R)).d (n + 1) n
        ≫ (chain_complex_x_iso_finsupp (R := R) X n).hom).hom).comp (Finsupp.lsingle σ)
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lsingle ((X.δ i) σ) := by
  classical
  have key : ModuleCat.ofHom (Finsupp.lsingle σ) ≫
      ((chain_complex_x_iso_finsupp (R := R) X (n + 1)).inv
        ≫ (X.chainComplex (ModuleCat.of R R)).d (n + 1) n
        ≫ (chain_complex_x_iso_finsupp (R := R) X n).hom)
      = ModuleCat.ofHom
          (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lsingle ((X.δ i) σ)) := by
    rw [← chain_complex_x_iso_finsupp_single]
    simp only [Category.assoc, Iso.hom_inv_id_assoc]
    rw [← Category.assoc, ιChainComplex_d]
    simp only [Preadditive.sum_comp, Preadditive.zsmul_comp, chain_complex_x_iso_finsupp_single]
    apply ModuleCat.hom_ext
    simp only [ModuleCat.hom_sum, ModuleCat.hom_zsmul, ModuleCat.hom_ofHom]
  have h := congrArg ModuleCat.Hom.hom key
  simpa using h

/-- The transported differential equals the alternating sum of `lmapDomain` along the faces.
Proves equality of linear maps out of `X _⦋n + 1⦌ →₀ R` on generators via `Finsupp.lhom_ext'`:
`transported_differential_on_generator` computes the transported differential on `lsingle σ`,
`lmapdomain_sum_on_generator` computes the right-hand sum on `lsingle σ`, and both give
`∑ i, (-1) ^ i • lsingle (X.δ i σ)`. -/
theorem transported_differential_eq_lmapdomain_sum
    {R : Type u} [Ring R] (X : SSet.{u}) (n : ℕ) :
    (((chain_complex_x_iso_finsupp (R := R) X (n + 1)).inv
        ≫ (X.chainComplex (ModuleCat.of R R)).d (n + 1) n
        ≫ (chain_complex_x_iso_finsupp (R := R) X n).hom).hom)
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R (X.δ i) := by
  apply Finsupp.lhom_ext'
  intro σ
  have h_lhs := transported_differential_on_generator (R := R) X n σ
  have h_rhs := lmapdomain_sum_on_generator (R := R) X n σ
  rw [h_lhs, h_rhs]

/-- The differential transported through `chain_complex_x_iso_finsupp` preserves
`Finsupp.supported R R (A.obj _)`. Decomposes as: the transported differential equals the
alternating sum of `Finsupp.lmapDomain` along the face maps `X.δ i` (`h_phi`); each face carries
a simplex of the subcomplex `A` to a simplex of `A` (`h_face`). Then `Finsupp.lmapDomain_supported`
+ `Finsupp.supported_mono` send each summand into `Finsupp.supported R R (A.obj ⦋n⦌)`. -/
theorem supported_d_stable
    {R : Type u} [Ring R] (X : SSet.{u}) (A : X.Subcomplex) (n : ℕ) :
    Submodule.map
      ((chain_complex_x_iso_finsupp (R := R) X (n + 1)).inv
        ≫ (X.chainComplex (ModuleCat.of R R)).d (n + 1) n
        ≫ (chain_complex_x_iso_finsupp (R := R) X n).hom).hom
      (Finsupp.supported R R (A.obj (Opposite.op ⦋n + 1⦌)))
      ≤ Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) := by
  have h_face := subcomplex_face_image_subset X A n
  have h_phi := transported_differential_eq_lmapdomain_sum (R := R) X n
  rw [h_phi, Submodule.map_le_iff_le_comap]
  intro x hx
  rw [Submodule.mem_comap, LinearMap.sum_apply]
  refine Submodule.sum_mem _ (fun i _ => ?_)
  rw [LinearMap.smul_apply]
  refine zsmul_mem ?_ _
  have hmem : Finsupp.lmapDomain R R (X.δ i) x
      ∈ Submodule.map (Finsupp.lmapDomain R R (X.δ i))
          (Finsupp.supported R R (A.obj (Opposite.op ⦋n + 1⦌))) := ⟨x, hx, rfl⟩
  rw [Finsupp.lmapDomain_supported] at hmem
  exact Finsupp.supported_mono (h_face i) hmem

/-- Hatcher §2.1 cone operator `b · (-)` on affine (LC) chains — prepends the apex vertex `b` to
every simplex via `Fin.cons b`. This is the engine from which both the barycentric subdivision `S`
and the chain homotopy `T` are built; kept as a bare `Finsupp.lmapDomain` (no wrapping) so the
cone boundary identity `affine_cone_boundary` can use `Finsupp.lmapDomain_comp` and `mapDomain`
composition lemmas cleanly. -/
noncomputable def affine_cone {R : Type u} [Ring R] {E : Type u} (b : E) (n : ℕ) :
    ((affine_sset E) _⦋n⦌ →₀ R) →ₗ[R] ((affine_sset E) _⦋n + 1⦌ →₀ R) :=
  Finsupp.lmapDomain R R (fun v => Fin.cons b v)

/-- The single reusable Mayer–Vietoris building block. For a subcomplex `A` of a simplicial set
`X`, this packages the chains supported in `A` (in the `Finsupp` model, via the degreewise iso
`chain_complex_x_iso_finsupp`) into an honest `ChainComplex (ModuleCat R) ℕ`, with differential
the restriction of the transported boundary and `d ∘ d = 0` inherited from `X.chainComplex`.
Instantiated at `A`, `B`, `A ⊓ B`, `A ⊔ B` it supplies the four sub-chain-complexes of the
Mayer–Vietoris short exact sequence. -/
noncomputable
def supported_chain_complex
    {R : Type u} [Ring R] (X : SSet.{u}) (A : X.Subcomplex) :
    ChainComplex (ModuleCat R) ℕ :=
  ChainComplex.of
    (fun n => ModuleCat.of R (Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌))))
    (fun n => ModuleCat.ofHom
      (LinearMap.restrict
        (((chain_complex_x_iso_finsupp (R := R) X (n + 1)).inv
            ≫ (X.chainComplex (ModuleCat.of R R)).d (n + 1) n
            ≫ (chain_complex_x_iso_finsupp (R := R) X n).hom).hom)
        (fun x hx => supported_d_stable X A n (Submodule.mem_map_of_mem hx))))
    (by
      intro n
      have hmor :
          (((chain_complex_x_iso_finsupp (R := R) X (n + 1 + 1)).inv
              ≫ (X.chainComplex (ModuleCat.of R R)).d (n + 1 + 1) (n + 1)
              ≫ (chain_complex_x_iso_finsupp (R := R) X (n + 1)).hom)
            ≫ ((chain_complex_x_iso_finsupp (R := R) X (n + 1)).inv
              ≫ (X.chainComplex (ModuleCat.of R R)).d (n + 1) n
              ≫ (chain_complex_x_iso_finsupp (R := R) X n).hom)) = 0 := by
        simp only [Category.assoc, Iso.hom_inv_id_assoc,
          HomologicalComplex.d_comp_d_assoc, zero_comp, comp_zero]
      apply ModuleCat.hom_ext
      rw [ModuleCat.hom_comp, ModuleCat.hom_ofHom, ModuleCat.hom_ofHom,
        ModuleCat.hom_zero, ← LinearMap.restrict_comp]
      apply LinearMap.ext
      intro y
      apply Subtype.ext
      rw [LinearMap.restrict_coe_apply, ← ModuleCat.hom_comp, hmor,
        ModuleCat.hom_zero]
      simp)

/-- The `0`-th face of an affine cone simplex recovers the base simplex: `δ 0 (Fin.cons b v) = v`.
Since `(affine_sset E).δ i` is precomposition with `Fin.succAbove i` and `Fin.succAbove 0 =
Fin.succ`, `Fin.cons_succ` collapses the cone. Together with its sibling `affine_delta_succ_cons`
this supplies the `i = 0` term of the cone boundary identity `affine_cone_boundary`. -/
theorem affine_delta_zero_cons {E : Type u} (b : E) (n : ℕ) (v : Fin (n + 1) → E) :
    (affine_sset E).δ (0 : Fin (n + 2)) (Fin.cons b v) = v := by trivial

/-- `(affine_sset E).δ i` is precomposition with `Fin.succAbove i` (definitionally, via
`TypeCat.ofHom (· ∘ ⇑…)`). After `funext j`, splitting `j` with `Fin.cases` gives: at `0`,
`Fin.succ_succAbove_zero` sends the index to `0` and `Fin.cons_zero` gives `b`; at `k.succ`,
`Fin.succ_succAbove_succ` gives `(i.succAbove k).succ` and `Fin.cons_succ` collapses both cones
to `v (i.succAbove k)`. -/
theorem affine_delta_succ_cons {E : Type u} (b : E) (n : ℕ) (i : Fin (n + 2))
    (v : Fin (n + 2) → E) :
    (affine_sset E).δ i.succ (Fin.cons b v) = Fin.cons b ((affine_sset E).δ i v) := by
  funext j
  refine Fin.cases ?_ (fun k => ?_) j
  · change (Fin.cons b v : Fin (n + 3) → E) (i.succ.succAbove 0) = b
    rw [Fin.succ_succAbove_zero, Fin.cons_zero]
  · change (Fin.cons b v : Fin (n + 3) → E) (i.succ.succAbove k.succ) = v (i.succAbove k)
    rw [Fin.succ_succAbove_succ, Fin.cons_succ]

/-- Naturality of the cone operator against face maps: both composites `δ i.succ ∘ₗ cone b` and
`cone b ∘ₗ δ i` are `Finsupp.lmapDomain` of a single underlying function (`δ i.succ ∘ Fin.cons b`
resp. `Fin.cons b ∘ δ i`), which agree pointwise by `affine_delta_succ_cons`. -/
theorem delta_succ_comp_cone {R : Type u} [Ring R] {E : Type u} (b : E) (n : ℕ) (i : Fin (n + 2)) :
    Finsupp.lmapDomain R R ((affine_sset E).δ i.succ) ∘ₗ affine_cone (R := R) b (n + 1)
      = affine_cone (R := R) b n ∘ₗ Finsupp.lmapDomain R R ((affine_sset E).δ i) := by
  change Finsupp.lmapDomain R R ((affine_sset E).δ i.succ) ∘ₗ
      Finsupp.lmapDomain R R (fun v => Fin.cons b v)
    = Finsupp.lmapDomain R R (fun v => Fin.cons b v) ∘ₗ
      Finsupp.lmapDomain R R ((affine_sset E).δ i)
  rw [← Finsupp.lmapDomain_comp, ← Finsupp.lmapDomain_comp]
  congr 1
  funext v
  exact affine_delta_succ_cons b n i v

/-- The `i = 0` face of the cone is the identity: `δ 0 ∘ (cons b)` collapses via
`Fin.succAbove_zero`/`Fin.cons_succ` to `v ↦ v` on generators, so `Finsupp.lmapDomain_comp` +
`Finsupp.lmapDomain_id` give `LinearMap.id`. -/
theorem delta_zero_comp_cone {R : Type u} [Ring R] {E : Type u} (b : E) (n : ℕ) :
    Finsupp.lmapDomain R R ((affine_sset E).δ (0 : Fin (n + 3))) ∘ₗ affine_cone (R := R) b (n + 1)
      = LinearMap.id := by
  unfold affine_cone
  rw [← Finsupp.lmapDomain_comp, ← Finsupp.lmapDomain_id (M := R) (R := R)]
  congr 1

/-- The cone boundary identity `∂ ∘ cone b = id − cone b ∘ ∂` for the affine simplicial set.
Distributes both composites over their alternating sums, then splits the degree-`(n + 2)` face
sum by `Fin.sum_univ_succ`: the `i = 0` term collapses to `id` (`delta_zero_comp_cone`), and each
`i.succ` term rewrites to `cone ∘ δ i` (`delta_succ_comp_cone`), the extra `(-1) ^ (i + 1)` sign
supplying the minus. -/
theorem affine_cone_boundary {R : Type u} [Ring R] {E : Type u} (b : E) (n : ℕ) :
    (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        ∘ₗ affine_cone (R := R) b (n + 1)
      = LinearMap.id - affine_cone (R := R) b n ∘ₗ
        (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i)) := by
  have h0 := delta_zero_comp_cone (R := R) b n
  have hs := fun i : Fin (n + 2) => delta_succ_comp_cone (R := R) b n i
  have hL : (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        ∘ₗ affine_cone (R := R) b (n + 1)
      = ∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) •
          (Finsupp.lmapDomain R R ((affine_sset E).δ i) ∘ₗ affine_cone (R := R) b (n + 1)) := by
    ext x
    simp only [LinearMap.comp_apply, LinearMap.sum_apply, LinearMap.smul_apply]
  have hR : affine_cone (R := R) b n ∘ₗ
        (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) •
          (affine_cone (R := R) b n ∘ₗ Finsupp.lmapDomain R R ((affine_sset E).δ i)) := by
    ext x
    simp only [LinearMap.comp_apply, LinearMap.sum_apply, LinearMap.smul_apply, map_sum,
      map_zsmul]
  rw [hL, hR, Fin.sum_univ_succ]
  simp only [Fin.val_zero, pow_zero, one_smul, h0]
  rw [sub_eq_add_neg, ← Finset.sum_neg_distrib]
  congr 1
  apply Finset.sum_congr rfl
  intro i _
  rw [hs i, Fin.val_succ, pow_succ, mul_smul, neg_one_smul, smul_neg]

/-- The degreewise inclusion `C(A) ↪ C(B)` of supported chain complexes for `A ≤ B`. In degree `n`
this is the subtype inclusion `Finsupp.supported R R (A.obj ⦋n⦌) ↪ (B.obj ⦋n⦌)`, valid by
`Finsupp.supported_mono` applied to `A.obj ≤ B.obj` (`Subfunctor.le_def`); it commutes with the
differential because both differentials are `restrict`s of the same transported boundary map. -/
noncomputable def supported_chain_complex_incl
    {R : Type u} [Ring R] (X : SSet.{u}) {A B : X.Subcomplex} (h : A ≤ B) :
    supported_chain_complex (R := R) X A ⟶ supported_chain_complex (R := R) X B where
  f n := ModuleCat.ofHom (Submodule.inclusion
    (Finsupp.supported_mono ((Subfunctor.le_def A B).1 h (Opposite.op ⦋n⦌))))
  comm' := by
    rintro i j rfl
    simp only [supported_chain_complex, ChainComplex.of_d]
    apply ModuleCat.hom_ext
    apply LinearMap.ext
    intro y
    apply Subtype.ext
    rfl

/-- Hatcher §2.1 barycentric subdivision operator `S` on affine (LC) chains, in the `Finsupp`
model — a same-degree endomorphism defined by recursion on `n`. Degree `0` is the identity; on a
generator `v : Fin (n + 2) → E`, `S(v) = b · S(∂ v)` where `b = Finset.univ.centroid ℝ v` is the
barycenter and `·` is the `affine_cone` apex operator. Built via `Finsupp.linearCombination` so it
stays linear for a noncommutative coefficient ring `R` (`Finsupp.lsum R` would demand
`SMulCommClass R R _`). This is the engine on which the chain-map identity `∂ ∘ S = S ∘ ∂`, the
chain homotopy `T` (`∂T + T∂ = S − id`), and ultimately the small-simplices quasi-isomorphism for
Mayer–Vietoris are built. -/
noncomputable def affine_sd {R : Type u} [Ring R] {E : Type u} [AddCommGroup E] [Module ℝ E]
    (n : ℕ) : ((affine_sset E) _⦋n⦌ →₀ R) →ₗ[R] ((affine_sset E) _⦋n⦌ →₀ R) := by
  induction n with
  | zero => exact LinearMap.id
  | succ n ih =>
      exact Finsupp.linearCombination R (fun v =>
        affine_cone (R := R) (Finset.univ.centroid ℝ v) n
          (ih ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
            • Finsupp.lmapDomain R R ((affine_sset E).δ i)) (Finsupp.single v 1))))

/-- `∂ ∘ ∂ = 0` for the `Finsupp` alternating-sum boundary of a general simplicial set `X`.
Conjugates each alternating sum back to the transported categorical differential via
`transported_differential_eq_lmapdomain_sum`, folds the two composites into one categorical
composite, cancels the middle iso pair `(chain_complex_x_iso_finsupp X (n + 1)).hom ≫ .inv = 𝟙`,
and finishes with `HomologicalComplex.d_comp_d`. -/
theorem finsupp_boundary_sq_zero {R : Type u} [Ring R] (X : SSet.{u}) (n : ℕ) :
    (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R (X.δ i)) ∘ₗ
      (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R (X.δ i)) = 0 := by
  rw [← transported_differential_eq_lmapdomain_sum (R := R) X n,
    ← transported_differential_eq_lmapdomain_sum (R := R) X (n + 1), ← ModuleCat.hom_comp]
  have hcomp :
      ((chain_complex_x_iso_finsupp (R := R) X (n + 2)).inv
          ≫ (X.chainComplex (ModuleCat.of R R)).d (n + 2) (n + 1)
          ≫ (chain_complex_x_iso_finsupp (R := R) X (n + 1)).hom)
        ≫ ((chain_complex_x_iso_finsupp (R := R) X (n + 1)).inv
          ≫ (X.chainComplex (ModuleCat.of R R)).d (n + 1) n
          ≫ (chain_complex_x_iso_finsupp (R := R) X n).hom) = 0 := by
    simp only [Category.assoc, Iso.hom_inv_id_assoc]
    rw [HomologicalComplex.d_comp_d_assoc]
    simp
  rw [hcomp, ModuleCat.hom_zero]

/-- The defining generator recursion of the barycentric subdivision operator `affine_sd`: on a
degree-`(n + 1)` generator `v : Fin (n + 2) → E`, `S(v) = b · S(∂ v)` where `b` is the barycenter
and `·` is `affine_cone`, matching the boundary shape used by `affine_cone_boundary`. -/
theorem affine_sd_succ_single {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] (n : ℕ) (v : Fin (n + 2) → E) :
    affine_sd (R := R) (n + 1) (Finsupp.single v 1)
      = affine_cone (R := R) (Finset.univ.centroid ℝ v) n
          (affine_sd (R := R) n
            ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((affine_sset E).δ i)) (Finsupp.single v 1))) := by
  simp [affine_sd, Finsupp.linearCombination_single, one_smul]

/-- The Mayer–Vietoris short complex `0 → C(A ⊓ B) → C(A) ⊕ C(B) → C(A ⊔ B) → 0`, packaged as a
`ShortComplex (ChainComplex (ModuleCat R) ℕ)`. The maps are built from the subcomplex-inclusion
morphism `supported_chain_complex_incl`, with the sign convention (minus on the second component
of the lift, plain `desc`) matching the algebraic model `submodule_inf_prod_sup_short_exact`. The
`f ≫ g = 0` obligation reduces to the fact that the two composite inclusions `A ⊓ B ↪ A ↪ A ⊔ B`
and `A ⊓ B ↪ B ↪ A ⊔ B` agree degreewise. -/
noncomputable def mv_short_complex {R : Type u} [Ring R] (X : SSet.{u})
    (A B : X.Subcomplex) :
    CategoryTheory.ShortComplex (ChainComplex (ModuleCat R) ℕ) :=
  ShortComplex.mk
    (biprod.lift
      (supported_chain_complex_incl X (inf_le_left : A ⊓ B ≤ A))
      (-(supported_chain_complex_incl X (inf_le_right : A ⊓ B ≤ B))))
    (biprod.desc
      (supported_chain_complex_incl X (le_sup_left : A ≤ A ⊔ B))
      (supported_chain_complex_incl X (le_sup_right : B ≤ A ⊔ B)))
    (by
      rw [biprod.lift_desc, Preadditive.neg_comp, add_neg_eq_zero]
      apply HomologicalComplex.hom_ext
      intro n
      simp only [HomologicalComplex.comp_f]
      apply ModuleCat.hom_ext
      apply LinearMap.ext
      intro y
      apply Subtype.ext
      rfl)

/-- `Finsupp.supported R R ((A ⊓ B).obj m) = Finsupp.supported R R (A.obj m) ⊓
Finsupp.supported R R (B.obj m)` at each simplicial degree. The subfunctor meet is objectwise
intersection (`Subfunctor.min_obj`), reducing the claim to `Finsupp.supported_inter`. -/
theorem supported_obj_inf {R : Type u} [Ring R] (X : SSet.{u}) (A B : X.Subcomplex)
    (m : SimplexCategoryᵒᵖ) :
    Finsupp.supported R R ((A ⊓ B).obj m) =
    Finsupp.supported R R (A.obj m) ⊓ Finsupp.supported R R (B.obj m) := by
  rw [CategoryTheory.Subfunctor.min_obj]
  exact Finsupp.supported_inter _ _

/-- The `i = 1` face of the degree-0 cone is the constant map to `b`. Since `δ 1 =
(Fin.last 1).succAbove = castSucc` and the unique index of `Fin 1` is `0`, we get
`(1 : Fin 2).succAbove 0 = 0`, whence `Fin.cons b v 0 = b` (`Fin.cons_zero`). -/
theorem delta_one_comp_cone_base {R : Type u} [Ring R] {E : Type u} (b : E) :
    Finsupp.lmapDomain R R ((affine_sset E).δ (1 : Fin 2)) ∘ₗ affine_cone (R := R) b 0
      = Finsupp.lmapDomain R R (fun _ : (affine_sset E) _⦋0⦌ => (fun _ : Fin 1 => b)) := by
  unfold affine_cone
  rw [← Finsupp.lmapDomain_comp]
  congr 1
  funext v j
  have hj : j = 0 := Fin.eq_zero j
  subst hj
  change (Fin.cons b v : Fin 2 → E) ((1 : Fin 2).succAbove 0) = b
  have h1 : (1 : Fin 2) = Fin.last 1 := rfl
  rw [h1, Fin.succAbove_last]
  simp

/-- Degree-0 base case of `δ 0 ∘ cone b = id`. Same argument as the sibling `delta_zero_comp_cone`
(which only covers degree `n + 1`): unfold the cone to `lmapDomain (Fin.cons b ·)`, fold the
composite via `Finsupp.lmapDomain_comp`, and identify the resulting function with `id` on
generators via `Fin.succAbove_zero`/`Fin.cons_succ`. -/
theorem delta_zero_comp_cone_base {R : Type u} [Ring R] {E : Type u} (b : E) :
    Finsupp.lmapDomain R R ((affine_sset E).δ (0 : Fin 2)) ∘ₗ affine_cone (R := R) b 0
      = LinearMap.id := by
  unfold affine_cone
  rw [← Finsupp.lmapDomain_comp, ← Finsupp.lmapDomain_id (M := R) (R := R)]
  congr 1

/-- The degree-0 cone boundary identity `∂ ∘ cone b = id − const_b`. Since `Fin 2 = {0, 1}`,
expanding the alternating sum via `Fin.sum_univ_two` reduces this to the two face cases
`δ 0 ∘ cone b = id` (`delta_zero_comp_cone_base`) and `δ 1 ∘ cone b = const_b`
(`delta_one_comp_cone_base`). -/
theorem affine_cone_zero_boundary {R : Type u} [Ring R] {E : Type u} (b : E) :
    (∑ i : Fin 2, (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        ∘ₗ affine_cone (R := R) b 0
      = LinearMap.id - Finsupp.lmapDomain R R
        (fun _ : (affine_sset E) _⦋0⦌ => (fun _ : Fin 1 => b)) := by
  have h_zero := delta_zero_comp_cone_base (R := R) b
  have h_one := delta_one_comp_cone_base (R := R) b
  rw [Fin.sum_univ_two]
  simp only [Fin.isValue, Fin.val_zero, pow_zero, one_smul, Fin.val_one, pow_one, neg_one_zsmul]
  rw [LinearMap.add_comp, LinearMap.neg_comp, h_zero, h_one]
  rw [← sub_eq_add_neg]
  rfl

/-- The submodule equality `Finsupp.supported R R (A.obj U) ⊓ Finsupp.supported R R (B.obj U) =
Finsupp.supported R R ((A ⊓ B).obj U)` (`supported_obj_inf`), transported to a `ModuleCat`
isomorphism via `LinearEquiv.ofEq`. -/
noncomputable def iso_inf {R : Type u} [Ring R] (X : SSet.{u})
    (A B : X.Subcomplex) (n : ℕ) :
    ModuleCat.of R ↥(Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ⊓
        Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌))) ≅
    (supported_chain_complex (R := R) X (A ⊓ B)).X n := by
  exact (LinearEquiv.ofEq _ _
    (supported_obj_inf X A B (Opposite.op ⦋n⦌)).symm).toModuleIso

/-- The `ModuleCat` product of the degree-`n` supports of `A` and `B` is isomorphic to the
degree-`n` term of the biproduct chain complex `supported_chain_complex X A ⊞
supported_chain_complex X B`, via `ModuleCat.biprodIsoProd` composed with
`HomologicalComplex.biprodXIso`. -/
noncomputable def iso_prod {R : Type u} [Ring R] (X : SSet.{u})
    (A B : X.Subcomplex) (n : ℕ) :
    ModuleCat.of R (↥(Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌))) ×
        ↥(Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)))) ≅
    (supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B).X n :=
  (ModuleCat.biprodIsoProd ((supported_chain_complex (R := R) X A).X n)
      ((supported_chain_complex (R := R) X B).X n)).symm ≪≫
    (HomologicalComplex.biprodXIso (supported_chain_complex (R := R) X A)
      (supported_chain_complex (R := R) X B) n).symm

/-- The submodule identity `Finsupp.supported R R (A.obj U) ⊔ Finsupp.supported R R (B.obj U) =
Finsupp.supported R R ((A ⊔ B).obj U)`, transported to a `ModuleCat` isomorphism. Follows from
`Subfunctor.max_obj` (the object of a sup of subfunctors is the union) together with
`Finsupp.supported_union`. -/
noncomputable def iso_sup {R : Type u} [Ring R] (X : SSet.{u})
    (A B : X.Subcomplex) (n : ℕ) :
    ModuleCat.of R ↥(Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ⊔
        Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌))) ≅
    (supported_chain_complex (R := R) X (A ⊔ B)).X n := by
  have h : Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ⊔
      Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)) =
      Finsupp.supported R R ((A ⊔ B).obj (Opposite.op ⦋n⦌)) := by
    rw [Subfunctor.max_obj, Finsupp.supported_union]
  exact (LinearEquiv.ofEq _ _ h).toModuleIso

/-- Commutativity of the left leg of the algebraic-vs-categorical Mayer–Vietoris short-complex
isomorphism: `iso_inf` followed by the evaluated `lift` map of `mv_short_complex` agrees with the
algebraic `prod` of inclusions followed by `iso_prod`. -/
theorem mv_iso_comm_left {R : Type u} [Ring R] (X : SSet.{u})
    (A B : X.Subcomplex) (n : ℕ) :
    (iso_inf X A B n).hom ≫ ((mv_short_complex (R := R) X A B).map
        (HomologicalComplex.eval (ModuleCat R) (ComplexShape.down ℕ) n)).f
      = ModuleCat.ofHom
          (LinearMap.prod
            (Submodule.inclusion (inf_le_left :
              Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ⊓
                Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)) ≤
                  Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌))))
            (-Submodule.inclusion (inf_le_right :
              Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ⊓
                Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)) ≤
                  Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)))))
        ≫ (iso_prod X A B n).hom := by
  simp only [ShortComplex.map_f, mv_short_complex, HomologicalComplex.eval_map]
  apply HomologicalComplex.biprodX_ext_to
  · erw [Category.assoc]
    erw [HomologicalComplex.biprod_lift_fst_f]
    erw [Category.assoc]
    erw [show (iso_prod X A B n).hom ≫ (biprod.fst :
        supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
          supported_chain_complex (R := R) X A).f n
        = ModuleCat.ofHom (LinearMap.fst R _ _) from by
      simp only [iso_prod, Iso.trans_hom, Iso.symm_hom]
      erw [Category.assoc]
      rw [show (HomologicalComplex.biprodXIso (supported_chain_complex (R := R) X A)
          (supported_chain_complex (R := R) X B) n).inv ≫ (biprod.fst :
            supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
              supported_chain_complex (R := R) X A).f n
          = biprod.fst from by
        rw [← HomologicalComplex.biprodXIso_hom_fst, Iso.inv_hom_id_assoc]]
      exact ModuleCat.biprodIsoProd_inv_comp_fst _ _]
    apply ModuleCat.hom_ext
    apply LinearMap.ext
    intro y
    apply Subtype.ext
    rfl
  · erw [Category.assoc]
    erw [HomologicalComplex.biprod_lift_snd_f]
    erw [Category.assoc]
    erw [show (iso_prod X A B n).hom ≫ (biprod.snd :
        supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
          supported_chain_complex (R := R) X B).f n
        = ModuleCat.ofHom (LinearMap.snd R _ _) from by
      simp only [iso_prod, Iso.trans_hom, Iso.symm_hom]
      erw [Category.assoc]
      rw [show (HomologicalComplex.biprodXIso (supported_chain_complex (R := R) X A)
          (supported_chain_complex (R := R) X B) n).inv ≫ (biprod.snd :
            supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
              supported_chain_complex (R := R) X B).f n
          = biprod.snd from by
        rw [← HomologicalComplex.biprodXIso_hom_snd, Iso.inv_hom_id_assoc]]
      exact ModuleCat.biprodIsoProd_inv_comp_snd _ _]
    apply ModuleCat.hom_ext
    apply LinearMap.ext
    intro y
    apply Subtype.ext
    rfl

/-- Commutativity of the right leg of the algebraic-vs-categorical Mayer–Vietoris short-complex
isomorphism (dual of `mv_iso_comm_left`): decomposes `(iso_prod X A B n).hom` via the biproduct
total identity `fst ≫ inl + snd ≫ inr = 𝟙`, then pushes the resulting sum through the desc map
`biprod.desc (supported_chain_complex_incl le_sup_left) (supported_chain_complex_incl
le_sup_right)`, matching it against the algebraic `coprod` of inclusions up to `iso_sup`. -/
theorem mv_iso_comm_right {R : Type u} [Ring R] (X : SSet.{u})
    (A B : X.Subcomplex) (n : ℕ) :
    (iso_prod X A B n).hom ≫ ((mv_short_complex (R := R) X A B).map
        (HomologicalComplex.eval (ModuleCat R) (ComplexShape.down ℕ) n)).g
      = ModuleCat.ofHom
          (LinearMap.coprod
            (Submodule.inclusion (le_sup_left :
              Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ≤
                Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ⊔
                  Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌))))
            (Submodule.inclusion (le_sup_right :
              Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)) ≤
                Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ⊔
                  Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)))))
        ≫ (iso_sup X A B n).hom := by
  simp only [ShortComplex.map_g, mv_short_complex, HomologicalComplex.eval_map]
  have hfst : (iso_prod X A B n).hom ≫ (biprod.fst :
      supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
        supported_chain_complex (R := R) X A).f n = ModuleCat.ofHom (LinearMap.fst R _ _) := by
    simp only [iso_prod, Iso.trans_hom, Iso.symm_hom]
    erw [Category.assoc]
    rw [show (HomologicalComplex.biprodXIso (supported_chain_complex (R := R) X A)
        (supported_chain_complex (R := R) X B) n).inv ≫ (biprod.fst :
          supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
            supported_chain_complex (R := R) X A).f n
        = biprod.fst from by
      rw [← HomologicalComplex.biprodXIso_hom_fst, Iso.inv_hom_id_assoc]]
    exact ModuleCat.biprodIsoProd_inv_comp_fst _ _
  have hsnd : (iso_prod X A B n).hom ≫ (biprod.snd :
      supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
        supported_chain_complex (R := R) X B).f n = ModuleCat.ofHom (LinearMap.snd R _ _) := by
    simp only [iso_prod, Iso.trans_hom, Iso.symm_hom]
    erw [Category.assoc]
    rw [show (HomologicalComplex.biprodXIso (supported_chain_complex (R := R) X A)
        (supported_chain_complex (R := R) X B) n).inv ≫ (biprod.snd :
          supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
            supported_chain_complex (R := R) X B).f n
        = biprod.snd from by
      rw [← HomologicalComplex.biprodXIso_hom_snd, Iso.inv_hom_id_assoc]]
    exact ModuleCat.biprodIsoProd_inv_comp_snd _ _
  have htot := HomologicalComplex.biprod_total_f
      (supported_chain_complex (R := R) X A) (supported_chain_complex (R := R) X B) n
  have hdecomp : (iso_prod X A B n).hom =
      ModuleCat.ofHom (LinearMap.fst R _ _) ≫ (biprod.inl :
        supported_chain_complex (R := R) X A ⟶
          supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B).f n +
      ModuleCat.ofHom (LinearMap.snd R _ _) ≫ (biprod.inr :
        supported_chain_complex (R := R) X B ⟶
          supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B).f n := by
    have e1 : ((iso_prod X A B n).hom ≫ (biprod.fst :
        supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
          supported_chain_complex (R := R) X A).f n) ≫ (biprod.inl :
        supported_chain_complex (R := R) X A ⟶
          supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B).f n
        = (iso_prod X A B n).hom ≫ ((biprod.fst :
            supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
              supported_chain_complex (R := R) X A).f n ≫ (biprod.inl :
            supported_chain_complex (R := R) X A ⟶
              supported_chain_complex (R := R) X A ⊞
                supported_chain_complex (R := R) X B).f n) := by
      erw [Category.assoc]
    have e2 : ((iso_prod X A B n).hom ≫ (biprod.snd :
        supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
          supported_chain_complex (R := R) X B).f n) ≫ (biprod.inr :
        supported_chain_complex (R := R) X B ⟶
          supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B).f n
        = (iso_prod X A B n).hom ≫ ((biprod.snd :
            supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B ⟶
              supported_chain_complex (R := R) X B).f n ≫ (biprod.inr :
            supported_chain_complex (R := R) X B ⟶
              supported_chain_complex (R := R) X A ⊞
                supported_chain_complex (R := R) X B).f n) := by
      erw [Category.assoc]
    rw [← hfst, ← hsnd]
    erw [e1, e2]
    rw [← Preadditive.comp_add, htot, Category.comp_id]
  rw [hdecomp]
  have f1 : (ModuleCat.ofHom (LinearMap.fst R
      (↥(Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌))))
      (↥(Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌))))) ≫ (biprod.inl :
        supported_chain_complex (R := R) X A ⟶
          supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B).f n) ≫
      (biprod.desc (supported_chain_complex_incl X (le_sup_left : A ≤ A ⊔ B))
        (supported_chain_complex_incl X (le_sup_right : B ≤ A ⊔ B))).f n
      = ModuleCat.ofHom (LinearMap.fst R
          (↥(Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌))))
          (↥(Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌))))) ≫
        (supported_chain_complex_incl X (le_sup_left : A ≤ A ⊔ B)).f n := by
    erw [Category.assoc, HomologicalComplex.biprod_inl_desc_f]
  have f2 : (ModuleCat.ofHom (LinearMap.snd R
      (↥(Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌))))
      (↥(Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌))))) ≫ (biprod.inr :
        supported_chain_complex (R := R) X B ⟶
          supported_chain_complex (R := R) X A ⊞ supported_chain_complex (R := R) X B).f n) ≫
      (biprod.desc (supported_chain_complex_incl X (le_sup_left : A ≤ A ⊔ B))
        (supported_chain_complex_incl X (le_sup_right : B ≤ A ⊔ B))).f n
      = ModuleCat.ofHom (LinearMap.snd R
          (↥(Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌))))
          (↥(Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌))))) ≫
        (supported_chain_complex_incl X (le_sup_right : B ≤ A ⊔ B)).f n := by
    erw [Category.assoc, HomologicalComplex.biprod_inr_desc_f]
  erw [Preadditive.add_comp]
  erw [f1, f2]
  apply ModuleCat.hom_ext
  apply LinearMap.ext
  rintro ⟨x, y⟩
  apply Subtype.ext
  rfl

/-- The algebraic short exact sequence `0 → (supp A ⊓ supp B) → (supp A) × (supp B) → (supp A ⊔
supp B) → 0` on the underlying `Finsupp` submodules is isomorphic, at each simplicial degree `n`,
to the categorical `mv_short_complex` evaluated at `n`. Assembled from the three degreewise
isomorphisms `iso_inf`, `iso_prod`, `iso_sup` and their commuting squares `mv_iso_comm_left`,
`mv_iso_comm_right` via `ShortComplex.isoMk`. -/
noncomputable def mv_map_eval_iso_algebraic {R : Type u} [Ring R] (X : SSet.{u})
    (A B : X.Subcomplex) (n : ℕ) :
    (ShortComplex.moduleCatMk
      (LinearMap.prod
        (Submodule.inclusion (inf_le_left :
          Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ⊓
            Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)) ≤
              Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌))))
        (-Submodule.inclusion (inf_le_right :
          Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ⊓
            Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)) ≤
              Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)))))
      (LinearMap.coprod
        (Submodule.inclusion (le_sup_left :
          Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ≤
            Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ⊔
              Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌))))
        (Submodule.inclusion (le_sup_right :
          Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)) ≤
            Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)) ⊔
              Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌)))))
      (by ext x; simp [Submodule.coe_inclusion])) ≅
    (mv_short_complex (R := R) X A B).map
      (HomologicalComplex.eval (ModuleCat R) (ComplexShape.down ℕ) n) := by
  exact ShortComplex.isoMk (iso_inf X A B n) (iso_prod X A B n) (iso_sup X A B n)
    (mv_iso_comm_left X A B n) (mv_iso_comm_right X A B n)

/-- Degreewise instance of the Mayer–Vietoris short exact sequence: at each simplicial degree
`n`, the sequence `0 → C(A ⊓ B)_n → C(A)_n ⊞ C(B)_n → C(A ⊔ B)_n → 0` obtained by evaluating
`mv_short_complex` is short exact. Follows from `submodule_inf_prod_sup_short_exact` transported
along the algebraic-vs-categorical comparison isomorphism `mv_map_eval_iso_algebraic`. -/
theorem mv_short_complex_degreewise_short_exact {R : Type u} [Ring R] (X : SSet.{u})
    (A B : X.Subcomplex) (n : ℕ) :
    ((mv_short_complex (R := R) X A B).map
      (HomologicalComplex.eval (ModuleCat R) (ComplexShape.down ℕ) n)).ShortExact := by
  have h_iso := mv_map_eval_iso_algebraic (R := R) X A B n
  exact ShortComplex.shortExact_of_iso h_iso
    (submodule_inf_prod_sup_short_exact
      (Finsupp.supported R R (A.obj (Opposite.op ⦋n⦌)))
      (Finsupp.supported R R (B.obj (Opposite.op ⦋n⦌))))

/-- The **Mayer–Vietoris short exact sequence** of chain complexes
`0 → C(A ⊓ B) → C(A) ⊞ C(B) → C(A ⊔ B) → 0`, for a subcomplex pair `A B` of a simplicial set `X`
(with chains valued in `Finsupp.supported R R`). Reduces to the degreewise statement
`mv_short_complex_degreewise_short_exact` via
`HomologicalComplex.shortExact_of_degreewise_shortExact`. -/
theorem mv_short_complex_short_exact {R : Type u} [Ring R] (X : SSet.{u})
    (A B : X.Subcomplex) :
    (mv_short_complex (R := R) X A B).ShortExact := by
  apply HomologicalComplex.shortExact_of_degreewise_shortExact
  intro n
  exact mv_short_complex_degreewise_short_exact X A B n

end Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
