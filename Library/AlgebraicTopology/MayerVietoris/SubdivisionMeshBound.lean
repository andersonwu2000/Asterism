import Mathlib.Algebra.Order.Ring.Star
import Mathlib.Analysis.Normed.Order.Lattice
import Mathlib.Data.Real.StarOrdered
import Library.AlgebraicTopology.MayerVietoris.AffineHomotopy
import Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
import Library.AlgebraicTopology.MayerVietoris.SingularSubdivisionHomotopy

/-!
# Mesh bound for iterated barycentric subdivision

This file proves the key geometric lemma behind the small simplices theorem for singular
homology (Hatcher, §2.1, Proposition 2.21): the diameter of the simplices produced by
barycentric subdivision of an affine `n`-simplex shrinks by a factor of `n / (n + 1)` at each
subdivision step, and hence tends to `0` under iteration. Combined with the singular
subdivision operator `singular_sd`, its chain homotopy `singular_ht` to the identity, and a
Lebesgue-number argument, this yields the small simplices theorem: for any open cover
`{A, B}` of a space `X` and any singular simplex `σ`, some iterate of subdivision of `σ`
decomposes the fundamental chain into pieces each mapping entirely into `A` or entirely
into `B`.

## Main statements

* `affine_sd_diam`: barycentric subdivision of an affine `n`-simplex with vertex set of
  diameter `D` produces simplices of diameter at most `(n / (n + 1)) * D`.
* `affine_sd_iter_diam` / `sd_mesh_exists_k`: iterating subdivision `k` times shrinks the
  diameter by `(n / (n + 1)) ^ k`, which can be made as small as desired.
* `singular_sd_supported` / `singular_ht_supported`: singular subdivision and its chain
  homotopy preserve the subcomplex of chains supported on simplices with image in a fixed
  set `U`.
* `singular_sd_iter_homotopy`: the iterated chain homotopy `H_k = ∑_{i < k} T ∘ Sⁱ` satisfies
  `∂ ∘ H_k + H_k ∘ ∂ = id - Sᵏ`.
* `singular_sd_lebesgue_cover`: the small simplices theorem — for an open cover `{A, B}` of
  `X`, some iterate of singular subdivision of any simplex `σ` decomposes into pieces each
  mapping entirely into `A` or entirely into `B`.

## Implementation notes

Several statements track the diameter bound `(n / (n + 1) : ℝ) ^ k * D` through an auxiliary
transport map `singular_transport`, which realizes an affine chain on the standard simplex as
a singular chain on `X` via a singular simplex `σ`.
-/

universe u

open CategoryTheory Simplicial
open Library.AlgebraicTopology.MayerVietoris.AffineHomotopy
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.MayerVietoris.SingularSubdivisionHomotopy
open Simplicial
open Simplicial CategoryTheory
open scoped Simplicial

namespace Library.AlgebraicTopology.MayerVietoris.SubdivisionMeshBound

/-- Singular subdivision preserves the subcomplex of chains supported on singular simplices
whose image lies in a fixed set `U`: if `x` is supported on `{σ | Set.range (toSSetObjEquiv
σ) ⊆ U}`, then so is `singular_sd n x`. -/
theorem singular_sd_supported {R : Type} [Ring R] {X : TopCat.{0}} (U : Set X) (n : ℕ) :
    ∀ x ∈ Finsupp.supported R R
        {σ : (TopCat.toSSet.obj X) _⦋n⦌ | Set.range ⇑(X.toSSetObjEquiv _ σ) ⊆ U},
      (@singular_sd R _ X n) x ∈ Finsupp.supported R R
        {σ : (TopCat.toSSet.obj X) _⦋n⦌ | Set.range ⇑(X.toSSetObjEquiv _ σ) ⊆ U} := by
  have hgen : ∀ σ : (TopCat.toSSet.obj X) _⦋n⦌,
      Set.range ⇑(X.toSSetObjEquiv _ σ) ⊆ U →
        (@singular_sd R _ X n) (Finsupp.single σ 1) ∈ Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ | Set.range ⇑(X.toSSetObjEquiv _ τ) ⊆ U} := by
    intro σ hσ
    simp only [singular_sd, Finsupp.linearCombination_single, one_smul]
    set f := (singular_transport σ).app (Opposite.op ⦋n⦌) with hf
    have hy : (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (affine_sd (R := R) n
            (Finsupp.single (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)))
        ∈ Finsupp.supported R R (Set.univ) := by
      rw [Finsupp.supported_univ]; exact Submodule.mem_top
    have hmem := (Finsupp.lmapDomain_supported R R f (Set.univ)) ▸ Submodule.mem_map_of_mem hy
    refine Finsupp.supported_mono ?_ hmem
    rintro τ ⟨w, -, rfl⟩
    exact fun z hz => hσ (singular_transport_range σ w hz)
  intro x hx
  have hmap : Submodule.map (@singular_sd R _ X n)
      (Finsupp.supported R R
        {σ : (TopCat.toSSet.obj X) _⦋n⦌ | Set.range ⇑(X.toSSetObjEquiv _ σ) ⊆ U}) ≤
      Finsupp.supported R R
        {σ : (TopCat.toSSet.obj X) _⦋n⦌ | Set.range ⇑(X.toSSetObjEquiv _ σ) ⊆ U} := by
    rw [Finsupp.supported_eq_span_single, Submodule.map_span_le]
    rintro _ ⟨σ, hσ, rfl⟩
    rw [← Finsupp.supported_eq_span_single]
    exact hgen σ hσ
  exact hmap (Submodule.mem_map_of_mem hx)

/-- The singular chain homotopy `singular_ht` sends a generator `Finsupp.single σ 1` with
image in `U` to a chain again supported on simplices with image in `U`. -/
theorem singular_ht_gen_supported {R : Type} [Ring R] {X : TopCat.{0}} (U : Set X) (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌) (hσ : Set.range ⇑(X.toSSetObjEquiv _ σ) ⊆ U) :
    (@singular_ht R _ X n) (Finsupp.single σ 1) ∈ Finsupp.supported R R
      {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ | Set.range ⇑(X.toSSetObjEquiv _ τ) ⊆ U} := by
  simp only [singular_ht, singular_ht, Finsupp.linearCombination_single, one_smul]
  set f := (singular_transport σ).app (Opposite.op ⦋n + 1⦌) with hf
  have hy : (Finsupp.subtypeDomain
        (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n + 1⦌ ↦
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
        (affine_ht (R := R) n
          (Finsupp.single (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)))
      ∈ Finsupp.supported R R (Set.univ) := by
    rw [Finsupp.supported_univ]; exact Submodule.mem_top
  have hmem := (Finsupp.lmapDomain_supported R R f (Set.univ)) ▸ Submodule.mem_map_of_mem hy
  refine Finsupp.supported_mono ?_ hmem
  rintro τ ⟨w, -, rfl⟩
  exact fun z hz => hσ (singular_transport_range σ w hz)

/-- Singular chain homotopy preserves the subcomplex of chains supported on singular simplices
whose image lies in a fixed set `U`. -/
theorem singular_ht_supported {R : Type} [Ring R] {X : TopCat.{0}} (U : Set X) (n : ℕ) :
    ∀ x ∈ Finsupp.supported R R
      {σ : (TopCat.toSSet.obj X) _⦋n⦌ | Set.range ⇑(X.toSSetObjEquiv _ σ) ⊆ U},
      (@singular_ht R _ X n x) ∈ Finsupp.supported R R
        {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ | Set.range ⇑(X.toSSetObjEquiv _ τ) ⊆ U} := by
  intro x hx
  suffices h : Submodule.map (@singular_ht R _ X n)
      (Finsupp.supported R R
        {σ : (TopCat.toSSet.obj X) _⦋n⦌ | Set.range ⇑(X.toSSetObjEquiv _ σ) ⊆ U})
      ≤ Finsupp.supported R R
        {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ | Set.range ⇑(X.toSSetObjEquiv _ τ) ⊆ U} by
    exact h (Submodule.mem_map_of_mem hx)
  rw [Finsupp.supported_eq_span_single, Submodule.map_span, Submodule.span_le]
  rintro _ ⟨_, ⟨σ, hσ, rfl⟩, rfl⟩
  exact singular_ht_gen_supported U n σ hσ

/-- Base case `n = 0` of the barycentric-subdivision diameter shrink: a single point has
convex hull of diameter `0`, matching the bound `0 / (0 + 1) * D = 0`. -/
theorem affine_sd_diam_base {R : Type u} [Ring R] {E : Type u}
    [NormedAddCommGroup E] [NormedSpace ℝ E] (v : Fin (0 + 1) → E) :
    affine_sd (R := R) 0 (Finsupp.single v 1) ∈
      Finsupp.supported R R
        {w : (affine_sset E) _⦋0⦌ |
          Metric.diam (convexHull ℝ (Set.range w)) ≤
            (↑(0 : ℕ) / (↑(0 : ℕ) + 1) : ℝ) *
              Metric.diam (convexHull ℝ (Set.range v))} := by
  rw [affine_sd_zero, LinearMap.id_apply]
  apply Finsupp.single_mem_supported
  simp only [Set.mem_setOf_eq, Nat.cast_zero, zero_div, zero_mul]
  haveI : Unique (Fin (0 + 1)) := inferInstanceAs (Unique (Fin 1))
  have hv := Set.range_unique (f := v)
  rw [hv, convexHull_singleton, Metric.diam_singleton]

/-- Barycentric subdivision `affine_sd n` commutes with the alternating boundary sum applied
to a generator: subdividing the boundary of `v` equals the alternating sum of the subdivided
faces `affine_sd n (Finsupp.single (δ i v) 1)`. -/
theorem affine_sd_boundary_expand {R : Type u} [Ring R] {E : Type u}
    [NormedAddCommGroup E] [NormedSpace ℝ E] (n : ℕ) (v : Fin (n + 1 + 1) → E) :
    affine_sd (R := R) n
        ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • Finsupp.lmapDomain R R ((affine_sset E).δ i)) (Finsupp.single v 1))
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • affine_sd (R := R) n (Finsupp.single ((affine_sset E).δ i v) 1) := by
  simp only [LinearMap.sum_apply, LinearMap.smul_apply, Finsupp.lmapDomain_apply,
    Finsupp.mapDomain_single, map_sum, map_zsmul]

/-- Every point of the convex hull of `Set.range v` lies within `(n + 1) / (n + 2)` of the
hull's diameter from the centroid of `v`. -/
theorem centroid_dist_le {E : Type u} [NormedAddCommGroup E] [NormedSpace ℝ E]
    (n : ℕ) (v : Fin (n + 1 + 1) → E) :
    ∀ x ∈ convexHull ℝ (Set.range v),
      dist (Finset.univ.centroid ℝ v) x ≤
        (↑(n + 1) / (↑(n + 1) + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) :=
  fun _x hx ↦
    Library.AlgebraicTopology.MayerVietoris.ShortExactComplex.centroid_dist_le_diam_mul
      (n + 1) v hx

/-- Adding a vertex `b` within distance `c` of `Set.range w` to a tuple of diameter at most
`c` keeps the diameter of the extended range at most `c`. -/
theorem cone_range_diam_le {E : Type u} [NormedAddCommGroup E]
    {n : ℕ} (b : E) (w : Fin (n + 1) → E) (c : ℝ)
    (hw : Metric.diam (Set.range w) ≤ c)
    (hb : ∀ x ∈ Set.range w, dist b x ≤ c) :
    Metric.diam (Set.range (Fin.cons b w)) ≤ c := by
  have hc0 : 0 ≤ c := le_trans Metric.diam_nonneg hw
  rw [Fin.range_cons]
  apply Metric.diam_le_of_forall_dist_le hc0
  intro x hx y hy
  rcases Set.mem_insert_iff.mp hx with rfl | hx2 <;>
    rcases Set.mem_insert_iff.mp hy with rfl | hy2
  · simpa using hc0
  · exact hb y hy2
  · rw [dist_comm]; exact hb x hx2
  · exact le_trans (Metric.dist_le_diam_of_mem (Set.finite_range w).isBounded hx2 hy2) hw

/-- Coning on the barycenter of `v` preserves the `(n + 1) / (n + 2) * D` diameter bound of
Hatcher's Proposition 2.21: subdividing faces bounded by diameter `D` and containment in the
hull of `Set.range v`, then coning on the centroid, keeps every resulting simplex within
diameter `D`. -/
theorem affine_cone_diam_supported {R : Type u} [Ring R] {E : Type u}
    [NormedAddCommGroup E] [NormedSpace ℝ E]
    (n : ℕ) (v : Fin (n + 1 + 1) → E)
    (y : ((affine_sset E) _⦋n⦌ →₀ R))
    (hy : y ∈ Finsupp.supported R R
      {w : (affine_sset E) _⦋n⦌ |
        Metric.diam (convexHull ℝ (Set.range w)) ≤
          (↑(n + 1) / (↑(n + 1) + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) ∧
        Set.range w ⊆ convexHull ℝ (Set.range v)}) :
    affine_cone (R := R) (Finset.univ.centroid ℝ v) n y ∈
      Finsupp.supported R R
        {w : (affine_sset E) _⦋n + 1⦌ |
          Metric.diam (convexHull ℝ (Set.range w)) ≤
            (↑(n + 1) / (↑(n + 1) + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v))} := by
  set b := Finset.univ.centroid ℝ v with hbdef
  set c : ℝ := (↑(n + 1) / (↑(n + 1) + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) with hcdef
  have himg : (fun (w : (affine_sset E) _⦋n⦌) ↦ Fin.cons b w) ''
      {w : (affine_sset E) _⦋n⦌ |
        Metric.diam (convexHull ℝ (Set.range w)) ≤ c ∧
        Set.range w ⊆ convexHull ℝ (Set.range v)} ⊆
      {w : (affine_sset E) _⦋n + 1⦌ |
        Metric.diam (convexHull ℝ (Set.range w)) ≤ c} := by
    rintro z ⟨w, ⟨hwdiam, hwsub⟩, rfl⟩
    change Metric.diam (convexHull ℝ (Set.range (Fin.cons b w))) ≤ c
    rw [convexHull_diam]
    apply cone_range_diam_le b w c
    · rw [← convexHull_diam]; exact hwdiam
    · intro x hx
      rw [hbdef]
      exact centroid_dist_le n v x (hwsub hx)
  apply Finsupp.supported_mono himg
  rw [← Finsupp.lmapDomain_supported]
  exact Submodule.mem_map_of_mem hy

/-- The range of a face `(affine_sset E).δ i v` is contained in the convex hull of
`Set.range v`. -/
theorem delta_range_subset_hull {E : Type u}
    [NormedAddCommGroup E] [NormedSpace ℝ E] (n : ℕ)
    (v : Fin (n + 1 + 1) → E) (i : Fin (n + 2)) :
    Set.range ((affine_sset E).δ i v) ⊆ convexHull ℝ (Set.range v) := by
  have hsub : Set.range ((affine_sset E).δ i v) ⊆ Set.range v := by
    rintro x ⟨j, rfl⟩
    exact ⟨i.succAbove j, rfl⟩
  exact hsub.trans (subset_convexHull ℝ (Set.range v))

/-- The diameter of the convex hull of a face's vertex range is bounded by the diameter of
the convex hull of the full vertex range. -/
theorem face_range_diam_le {E : Type u}
    [NormedAddCommGroup E] [NormedSpace ℝ E] (n : ℕ)
    (v : Fin (n + 1 + 1) → E) (i : Fin (n + 2)) :
    Metric.diam (convexHull ℝ (Set.range ((affine_sset E).δ i v))) ≤
      Metric.diam (convexHull ℝ (Set.range v)) := by
  have hsub : convexHull ℝ (Set.range ((affine_sset E).δ i v)) ⊆
      convexHull ℝ (Set.range v) :=
    convexHull_min (delta_range_subset_hull n v i) (convex_convexHull ℝ (Set.range v))
  exact Metric.diam_mono hsub
    (isBounded_convexHull.mpr (Set.finite_range v).isBounded)

/-- Per-face diameter bound for one subdivision step: given the inductive diameter bound for
subdivisions of an `n`-simplex, the subdivision of a face `δ i v` of an `(n + 1)`-simplex lies
in the target `(n + 1) / (n + 2) * D` diameter bound. -/
theorem sd_face_diam_bound {R : Type u} [Ring R] {E : Type u}
    [NormedAddCommGroup E] [NormedSpace ℝ E] (n : ℕ)
    (ih : ∀ u : Fin (n + 1) → E,
      affine_sd (R := R) n (Finsupp.single u 1) ∈
        Finsupp.supported R R
          {w : (affine_sset E) _⦋n⦌ |
            Metric.diam (convexHull ℝ (Set.range w)) ≤
              (↑n / (↑n + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range u))})
    (v : Fin (n + 1 + 1) → E) (i : Fin (n + 2)) :
    affine_sd (R := R) n (Finsupp.single ((affine_sset E).δ i v) 1) ∈
      Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ |
          Metric.diam (convexHull ℝ (Set.range w)) ≤
          (↑(n + 1) / (↑(n + 1) + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v))} := by
  have hdiam :
      Metric.diam (convexHull ℝ (Set.range ((affine_sset E).δ i v)))
        ≤ Metric.diam (convexHull ℝ (Set.range v)) := face_range_diam_le n v i
  have hkey :
      (↑n / (↑n + 1) : ℝ) *
          Metric.diam (convexHull ℝ (Set.range ((affine_sset E).δ i v)))
        ≤ (↑(n + 1) / (↑(n + 1) + 1) : ℝ) *
            Metric.diam (convexHull ℝ (Set.range v)) := by
    have hdnn : 0 ≤ Metric.diam (convexHull ℝ (Set.range v)) := Metric.diam_nonneg
    have hcoef : (↑n / (↑n + 1) : ℝ) ≤ (↑(n + 1) / (↑(n + 1) + 1) : ℝ) := by
      rw [div_le_div_iff₀ (by positivity) (by positivity)]; push_cast; nlinarith
    calc
      (↑n / (↑n + 1) : ℝ) *
            Metric.diam (convexHull ℝ (Set.range ((affine_sset E).δ i v)))
          ≤ (↑n / (↑n + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) := by
            gcongr
      _ ≤ (↑(n + 1) / (↑(n + 1) + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) := by
            gcongr
  have hsub :
      {w : (affine_sset E) _⦋n⦌ |
          Metric.diam (convexHull ℝ (Set.range w)) ≤
            (↑n / (↑n + 1) : ℝ) *
              Metric.diam (convexHull ℝ (Set.range ((affine_sset E).δ i v)))} ⊆
        {w : (affine_sset E) _⦋n⦌ |
          Metric.diam (convexHull ℝ (Set.range w)) ≤
            (↑(n + 1) / (↑(n + 1) + 1) : ℝ) *
              Metric.diam (convexHull ℝ (Set.range v))} := by
    intro w hw
    exact le_trans hw hkey
  exact Finsupp.supported_mono hsub (ih ((affine_sset E).δ i v))

/-- Each subdivided face `affine_sd n (Finsupp.single (δ i v) 1)` satisfies both the diameter
bound of `sd_face_diam_bound` and the containment of its range in the convex hull of
`Set.range v`. -/
theorem affine_sd_face_term_supported {R : Type u} [Ring R] {E : Type u}
    [NormedAddCommGroup E] [NormedSpace ℝ E] (n : ℕ)
    (ih : ∀ u : Fin (n + 1) → E,
      affine_sd (R := R) n (Finsupp.single u 1) ∈
        Finsupp.supported R R
          {w : (affine_sset E) _⦋n⦌ |
            Metric.diam (convexHull ℝ (Set.range w)) ≤
              (↑n / (↑n + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range u))})
    (v : Fin (n + 1 + 1) → E) :
    ∀ i : Fin (n + 2),
      affine_sd (R := R) n (Finsupp.single ((affine_sset E).δ i v) 1) ∈
        Finsupp.supported R R
          {w : (affine_sset E) _⦋n⦌ |
            Metric.diam (convexHull ℝ (Set.range w)) ≤
              (↑(n + 1) / (↑(n + 1) + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) ∧
            Set.range w ⊆ convexHull ℝ (Set.range v)} := by
  intro i
  have hrange : Set.range ((affine_sset E).δ i v) ⊆ convexHull ℝ (Set.range v) :=
    delta_range_subset_hull n v i
  have hdiam : affine_sd (R := R) n (Finsupp.single ((affine_sset E).δ i v) 1) ∈
      Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ |
          Metric.diam (convexHull ℝ (Set.range w)) ≤
            (↑(n + 1) / (↑(n + 1) + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v))} :=
    sd_face_diam_bound n ih v i
  have hrng : affine_sd (R := R) n (Finsupp.single ((affine_sset E).δ i v) 1) ∈
      Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ convexHull ℝ (Set.range v)} :=
    affine_sd_supported (convex_convexHull ℝ (Set.range v)) n _
      (Finsupp.single_mem_supported R 1 hrange)
  rw [Finsupp.mem_supported] at hdiam hrng ⊢
  intro x hx
  exact ⟨hdiam hx, hrng hx⟩

/-- Subdividing the boundary of an `(n + 1)`-simplex `v` lands every resulting face in the
target diameter-and-range-containment support set. -/
theorem affine_sd_subdiv_faces {R : Type u} [Ring R] {E : Type u}
    [NormedAddCommGroup E] [NormedSpace ℝ E] (n : ℕ)
    (ih : ∀ u : Fin (n + 1) → E,
      affine_sd (R := R) n (Finsupp.single u 1) ∈
        Finsupp.supported R R
          {w : (affine_sset E) _⦋n⦌ |
            Metric.diam (convexHull ℝ (Set.range w)) ≤
              (↑n / (↑n + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range u))})
    (v : Fin (n + 1 + 1) → E) :
    affine_sd (R := R) n
        ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • Finsupp.lmapDomain R R ((affine_sset E).δ i)) (Finsupp.single v 1)) ∈
      Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ |
          Metric.diam (convexHull ℝ (Set.range w)) ≤
            (↑(n + 1) / (↑(n + 1) + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) ∧
            Set.range w ⊆ convexHull ℝ (Set.range v)} := by
  have hexpand : affine_sd (R := R) n
        ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • Finsupp.lmapDomain R R ((affine_sset E).δ i)) (Finsupp.single v 1))
      = ∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • affine_sd (R := R) n (Finsupp.single ((affine_sset E).δ i v) 1) :=
    affine_sd_boundary_expand n v
  have hterm : ∀ i : Fin (n + 2),
      affine_sd (R := R) n (Finsupp.single ((affine_sset E).δ i v) 1) ∈
        Finsupp.supported R R
          {w : (affine_sset E) _⦋n⦌ |
            Metric.diam (convexHull ℝ (Set.range w)) ≤
              (↑(n + 1) / (↑(n + 1) + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v)) ∧
            Set.range w ⊆ convexHull ℝ (Set.range v)} :=
    affine_sd_face_term_supported n ih v
  rw [hexpand]
  refine Submodule.sum_mem _ fun i _ ↦ ?_
  exact zsmul_mem (hterm i) _

/-- **Barycentric subdivision diameter bound** (Hatcher, Proposition 2.21): subdividing an
affine `n`-simplex with vertex tuple `v` produces simplices whose convex hull has diameter at
most `(n / (n + 1)) * Metric.diam (convexHull ℝ (Set.range v))`. Proved by induction on `n`,
coning the inductive bound on the subdivided boundary onto the barycenter. -/
theorem affine_sd_diam
    {R : Type u} [Ring R] {E : Type u} [NormedAddCommGroup E] [NormedSpace ℝ E]
    (n : ℕ) (v : Fin (n + 1) → E) :
    affine_sd (R := R) n (Finsupp.single v 1) ∈
      Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ |
          Metric.diam (convexHull ℝ (Set.range w)) ≤
            (n / (n + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v))} := by
  induction n with
  | zero => exact affine_sd_diam_base v
  | succ n ih =>
      rw [affine_sd_succ_single]
      exact affine_cone_diam_supported n v _ (affine_sd_subdiv_faces n ih v)

/-- Chain-level form of `affine_sd_diam`: subdivision maps any chain supported on simplices
of diameter at most `D` to a chain supported on simplices of diameter at most
`(n / (n + 1)) * D`. -/
theorem affine_sd_diam_supported {R : Type u} [Ring R] {E : Type u}
    [NormedAddCommGroup E] [NormedSpace ℝ E] (n : ℕ) (D : ℝ) :
    ∀ x ∈ Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ | Metric.diam (convexHull ℝ (Set.range w)) ≤ D},
      affine_sd (R := R) n x ∈ Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ |
          Metric.diam (convexHull ℝ (Set.range w)) ≤ (n / (n + 1) : ℝ) * D} := by
  intro x hx
  rw [Finsupp.supported_eq_span_single] at hx
  induction hx using Submodule.span_induction with
  | mem y hy =>
      obtain ⟨v, hv, rfl⟩ := hy
      have hv' : Metric.diam (convexHull ℝ (Set.range v)) ≤ D := hv
      have hsub : {w : (affine_sset E) _⦋n⦌ |
            Metric.diam (convexHull ℝ (Set.range w)) ≤
              (n / (n + 1) : ℝ) * Metric.diam (convexHull ℝ (Set.range v))} ⊆
          {w : (affine_sset E) _⦋n⦌ |
            Metric.diam (convexHull ℝ (Set.range w)) ≤ (n / (n + 1) : ℝ) * D} := by
        intro w hw
        exact le_trans hw (mul_le_mul_of_nonneg_left hv' (by positivity))
      exact Finsupp.supported_mono hsub (affine_sd_diam n v)
  | zero => simp
  | add a b _ _ ha hb => rw [map_add]; exact Submodule.add_mem _ ha hb
  | smul r a _ ha => rw [map_smul]; exact Submodule.smul_mem _ _ ha

/-- Restatement of `affine_sd_diam_supported` as the single-step contraction used to build
the iterated mesh bound. -/
theorem sd_step_diam {R : Type u} [Ring R] {E : Type u}
    [NormedAddCommGroup E] [NormedSpace ℝ E] (n : ℕ) (D : ℝ) :
    ∀ x ∈ Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ | Metric.diam (convexHull ℝ (Set.range w)) ≤ D},
      affine_sd (R := R) n x ∈ Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ |
          Metric.diam (convexHull ℝ (Set.range w)) ≤ (n / (n + 1) : ℝ) * D} :=
  affine_sd_diam_supported n D

/-- Iterating barycentric subdivision `k` times shrinks the diameter bound geometrically:
a chain supported on simplices of diameter at most `D` is sent by `(affine_sd n) ^ k` to a
chain supported on simplices of diameter at most `(n / (n + 1)) ^ k * D`. -/
theorem affine_sd_iter_diam {R : Type u} [Ring R] {E : Type u}
    [NormedAddCommGroup E] [NormedSpace ℝ E] (n : ℕ) (D : ℝ) (k : ℕ) :
    ∀ x ∈ Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ | Metric.diam (convexHull ℝ (Set.range w)) ≤ D},
      ((affine_sd (R := R) (E := E) n) ^ k) x ∈ Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ |
          Metric.diam (convexHull ℝ (Set.range w)) ≤ (n / (n + 1) : ℝ) ^ k * D} := by
  induction k with
  | zero =>
    intro x hx
    simpa using hx
  | succ k ih =>
    intro x hx
    have hstep := sd_step_diam (R := R) (E := E) n ((n / (n + 1) : ℝ) ^ k * D)
      ((affine_sd (R := R) (E := E) n ^ k) x) (ih x hx)
    have hbound : (n / (n + 1) : ℝ) * ((n / (n + 1) : ℝ) ^ k * D)
        = (n / (n + 1) : ℝ) ^ (k + 1) * D := by ring
    rw [hbound] at hstep
    have hcomp : (affine_sd (R := R) (E := E) n ^ (k + 1)) x
        = affine_sd (R := R) n ((affine_sd (R := R) (E := E) n ^ k) x) := by
      rw [pow_succ']; rfl
    rw [hcomp]
    exact hstep

/-- Barycentric associativity of `affine_simplex_map`: realizing a simplex `u`, then
realizing the result via `w`, agrees with realizing the composed vertex tuple
`i ↦ affine_simplex_map w ⟨u i, _⟩`. -/
theorem affine_simplex_map_assoc {n m l : ℕ}
    (w : {v : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ // Set.range v ⊆ stdSimplex ℝ (Fin (n + 1))})
    (u : {v : (affine_sset (Fin (m + 1) → ℝ)) _⦋l⦌ // Set.range v ⊆ stdSimplex ℝ (Fin (m + 1))})
    (z : stdSimplex ℝ (Fin (l + 1))) :
    affine_simplex_map w.1 ⟨affine_simplex_map u.1 z,
        affine_simplex_map_mem_of_convex (convex_stdSimplex ℝ (Fin (m + 1))) u.2 z⟩ =
      affine_simplex_map
        (fun i ↦ affine_simplex_map w.1 ⟨u.1 i, u.2 (Set.mem_range_self i)⟩) z := by
  simp only [affine_simplex_map, ContinuousMap.coe_mk]
  change ∑ i, (∑ j, z.val j • u.1 j) i • w.1 i
      = ∑ j, z.val j • ∑ i, u.1 j i • w.1 i
  simp only [Finset.sum_apply, Pi.smul_apply, Finset.sum_smul, Finset.smul_sum, smul_assoc]
  rw [Finset.sum_comm]

/-- Composition law for singular transports: transporting along `w` and then along `u`
agrees with transporting directly along the composed affine simplex map. -/
theorem singular_transport_comp {X : TopCat.{0}} {n m l : ℕ}
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (w : {v : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ // Set.range v ⊆ stdSimplex ℝ (Fin (n + 1))})
    (u : {v : (affine_sset (Fin (m + 1) → ℝ)) _⦋l⦌ // Set.range v ⊆ stdSimplex ℝ (Fin (m + 1))}) :
    (singular_transport ((singular_transport σ).app (Opposite.op ⦋m⦌) w)).app (Opposite.op ⦋l⦌) u =
      (singular_transport σ).app (Opposite.op ⦋l⦌)
        ⟨fun i ↦ affine_simplex_map w.1 ⟨u.1 i, u.2 (Set.mem_range_self i)⟩,
          Set.range_subset_iff.mpr fun i ↦ affine_simplex_map_mem_of_convex
            (convex_stdSimplex ℝ (Fin (n + 1))) w.2 ⟨u.1 i, u.2 (Set.mem_range_self i)⟩⟩ := by
  apply (X.toSSetObjEquiv (Opposite.op ⦋l⦌)).injective
  apply ContinuousMap.ext
  intro z
  simp only [singular_transport_app_eval]
  congr 1
  apply Subtype.ext
  exact affine_simplex_map_assoc w u z

/-- The `k`-th power of singular subdivision is a chain map: `Sᵏ ∘ ∂ = ∂ ∘ Sᵏ`. -/
theorem singular_sd_pow_boundary {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ) :
    ((singular_sd (R := R) (X := X) n) ^ k) ∘ₗ
      (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
    = (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
      ∘ₗ ((singular_sd (R := R) (X := X) (n + 1)) ^ k) := by
  exact Module.End.commute_pow_left_of_commute (singular_sd_boundary n).symm k

/-- Single-step telescoping identity `∂ (T ∘ Sᵏ) + (T ∘ Sᵏ) ∘ ∂ = Sᵏ - Sᵏ⁺¹`, obtained by
conjugating the chain-homotopy identity `∂T + T∂ = id - S` by the `k`-th power of singular
subdivision. -/
theorem singular_iter_homotopy_step {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ) :
    (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) ∘ₗ
        ((@singular_ht R _ X (n + 1)) ∘ₗ ((singular_sd (R := R) (X := X) (n + 1)) ^ k))
      + ((@singular_ht R _ X n) ∘ₗ ((singular_sd (R := R) (X := X) n) ^ k)) ∘ₗ
        (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
      = ((singular_sd (R := R) (X := X) (n + 1)) ^ k)
          - ((singular_sd (R := R) (X := X) (n + 1)) ^ (k + 1)) := by
  have hcomm :
      ((singular_sd (R := R) (X := X) n) ^ k) ∘ₗ
        (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
      = (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
        ∘ₗ ((singular_sd (R := R) (X := X) (n + 1)) ^ k) := singular_sd_pow_boundary n k
  have hht := singular_ht_boundary (R := R) (X := X) n
  rw [LinearMap.comp_assoc, hcomm, ← LinearMap.comp_assoc, ← LinearMap.comp_assoc,
      ← LinearMap.add_comp, hht, LinearMap.sub_comp, LinearMap.id_comp,
      ← Module.End.iterate_succ']

/-- Iterated Hatcher prism identity `∂ ∘ H_k + H_k ∘ ∂ = id - Sᵏ`, where
`H_k = ∑_{i < k} T ∘ Sⁱ` telescopes the single-step homotopies. -/
theorem singular_sd_iter_homotopy {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ) :
    (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) ∘ₗ
        (∑ i ∈ Finset.range k,
          (@singular_ht R _ X (n + 1)) ∘ₗ ((singular_sd (R := R) (X := X) (n + 1)) ^ i))
      + (∑ i ∈ Finset.range k, (@singular_ht R _ X n) ∘ₗ ((singular_sd (R := R) (X := X) n) ^ i)) ∘ₗ
        (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
      = LinearMap.id - ((singular_sd (R := R) (X := X) (n + 1)) ^ k) := by
  induction k with
  | zero => simp [Module.End.one_eq_id]
  | succ k ih =>
    have hstep := singular_iter_homotopy_step (R := R) (X := X) n k
    rw [Finset.sum_range_succ, Finset.sum_range_succ, LinearMap.comp_add, LinearMap.add_comp,
        add_add_add_comm, ih, hstep]
    abel

/-- Weakening of `singular_transport_range`: if `σ` maps the convex hull of `Set.range w`
into `U`, then transporting `w` along `σ` produces a singular simplex whose image also lies
in `U`. -/
theorem singular_transport_range_hull
    {X : TopCat.{0}} {n m : ℕ} (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (w : {v : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ //
        Set.range v ⊆ stdSimplex ℝ (Fin (n + 1))})
    (U : Set X)
    (hU : ∀ p : stdSimplex ℝ (Fin (n + 1)),
        (p : Fin (n + 1) → ℝ) ∈ convexHull ℝ (Set.range w.1) →
        X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ p ∈ U) :
    Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋m⦌)
        ((singular_transport σ).app (Opposite.op ⦋m⦌) w)) ⊆ U := by
  rw [Set.range_subset_iff]
  intro z
  rw [singular_transport_app_eval σ w z]
  apply hU
  exact affine_simplex_map_range_subset_convexHull w.1 (Set.mem_range_self z)

/-- The fundamental affine tuple transports along `σ` back to `σ` itself, at any degree `n`. -/
theorem singular_transport_fund_single_gen {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (Finsupp.single (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))
      = Finsupp.single σ 1 := by
  have hw : Set.range (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) ⊆
      stdSimplex ℝ (Fin (n + 1)) := by
    rintro _ ⟨i, rfl⟩
    exact single_mem_stdSimplex ℝ i
  have hsub :
      Finsupp.subtypeDomain (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
        (Finsupp.single (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) (1 : R))
      = Finsupp.single
          (⟨fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ), hw⟩ :
            {v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ //
              Set.range v ⊆ stdSimplex ℝ (Fin (n + 1))}) (1 : R) := by
    classical
    apply Finsupp.ext
    intro a
    simp only [Finsupp.subtypeDomain_apply, Finsupp.single_apply, Subtype.ext_iff]
  rw [hsub, Finsupp.lmapDomain_apply]
  have hmd : Finsupp.mapDomain (⇑((singular_transport σ).app (Opposite.op ⦋n⦌)))
      (Finsupp.single
        (⟨fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ), hw⟩ :
          {v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ //
            Set.range v ⊆ stdSimplex ℝ (Fin (n + 1))}) (1 : R))
      = Finsupp.single (((singular_transport σ).app (Opposite.op ⦋n⦌))
          ⟨fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ), hw⟩) (1 : R) :=
    Finsupp.mapDomain_single
  refine hmd.trans ?_
  congr 1
  apply (X.toSSetObjEquiv (Opposite.op ⦋n⦌)).injective
  apply ContinuousMap.ext
  intro z
  have hz := singular_transport_app_eval σ
    (⟨fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ), hw⟩ :
      {v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ //
        Set.range v ⊆ stdSimplex ℝ (Fin (n + 1))}) z
  exact hz.trans (congrArg (fun p ↦ (X.toSSetObjEquiv (Opposite.op ⦋n⦌)) σ p)
    (Subtype.ext (affine_simplex_map_single_tuple z)))

/-- `Finsupp.lmapDomain f c` lands in `Finsupp.supported SA ⊔ Finsupp.supported SB` whenever
every point of `c`'s support maps under `f` into `SA` or into `SB`. -/
theorem lmap_mem_sup_supported {R : Type} [Ring R] {α β : Type}
    (f : α → β) (c : α →₀ R) (SA SB : Set β)
    (h : ∀ a ∈ c.support, f a ∈ SA ∨ f a ∈ SB) :
    Finsupp.lmapDomain R R f c ∈ Finsupp.supported R R SA ⊔ Finsupp.supported R R SB := by
  classical
  rw [← Finsupp.supported_union, Finsupp.mem_supported]
  intro x hx
  rw [Finsupp.lmapDomain_apply] at hx
  have hx2 := Finsupp.mapDomain_support hx
  rw [Finset.mem_image] at hx2
  obtain ⟨a, ha, rfl⟩ := hx2
  exact h a ha

/-- Lebesgue number for the open cover `{σ̃⁻¹A, σ̃⁻¹B}` of the compact standard simplex, where
`σ̃` is the continuous map realizing the singular simplex `σ`: there is `δ > 0` such that every
`δ`-ball around a point of the simplex maps entirely into `A` or entirely into `B`. -/
theorem lebesgue_radius
    {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ)
    (n : ℕ) (σ : (TopCat.toSSet.obj X) _⦋n⦌) :
    ∃ δ : ℝ, 0 < δ ∧ ∀ x : stdSimplex ℝ (Fin (n + 1)),
      (∀ y : stdSimplex ℝ (Fin (n + 1)),
          dist (x : Fin (n + 1) → ℝ) (y : Fin (n + 1) → ℝ) < δ →
          X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ y ∈ A) ∨
      (∀ y : stdSimplex ℝ (Fin (n + 1)),
          dist (x : Fin (n + 1) → ℝ) (y : Fin (n + 1) → ℝ) < δ →
          X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ y ∈ B) := by
  classical
  have hcpt : IsCompact (Set.univ : Set (stdSimplex ℝ (Fin (n + 1)))) := isCompact_univ
  set f := X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ with hf
  obtain ⟨δ, hδ, hcov⟩ := lebesgue_number_lemma_of_metric (s := Set.univ)
    (c := fun b : Bool ↦ ⇑f ⁻¹' (bif b then A else B)) hcpt
    (by
      intro b
      cases b
      · exact hB.preimage f.continuous
      · exact hA.preimage f.continuous)
    (by
      intro p _
      rw [Set.mem_iUnion]
      have hpp : f p ∈ A ∪ B := by rw [hAB]; exact Set.mem_univ _
      rcases hpp with h | h
      · exact ⟨true, h⟩
      · exact ⟨false, h⟩)
  refine ⟨δ, hδ, fun x ↦ ?_⟩
  obtain ⟨i, hi⟩ := hcov x (Set.mem_univ x)
  cases i with
  | true =>
      left
      intro y hy
      have hyb : y ∈ Metric.ball x δ := by
        rw [Metric.mem_ball', Subtype.dist_eq]; exact hy
      exact hi hyb
  | false =>
      right
      intro y hy
      have hyb : y ∈ Metric.ball x δ := by
        rw [Metric.mem_ball', Subtype.dist_eq]; exact hy
      exact hi hyb

/-- The geometric decay `(n / (n + 1)) ^ k` eventually beats any target `δ > 0`, for any
starting diameter `D`. -/
theorem sd_mesh_exists_k (n : ℕ) (D δ : ℝ) (hD : 0 ≤ D) (hδ : 0 < δ) :
    ∃ k : ℕ, (n / (n + 1) : ℝ) ^ k * D ≤ δ := by
  rcases hD.eq_or_lt with hD0 | hDpos
  · exact ⟨0, by simp [← hD0, hδ.le]⟩
  · have hratio : (n / (n + 1) : ℝ) < 1 := by
      rw [div_lt_one (by positivity)]
      linarith
    obtain ⟨k, hk⟩ := exists_pow_lt_of_lt_one (div_pos hδ hDpos) hratio
    exact ⟨k, (lt_div_iff₀ hDpos).mp hk |>.le⟩

/-- Iterating singular subdivision of the fundamental simplex enough times drives the mesh
(the maximal diameter of the subdivided pieces) below any prescribed `δ > 0`. -/
theorem singular_sd_iter_mesh_small {R : Type} [Ring R] (n : ℕ) :
    ∀ δ : ℝ, 0 < δ → ∃ k : ℕ, ∀ w ∈ (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (((affine_sd (R := R) n) ^ k)
            (Finsupp.single (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))).support,
      Metric.diam (convexHull ℝ (Set.range w.1)) ≤ δ := by
  intro δ hδ
  set v0 : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ :=
    (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) with hv0
  set D := Metric.diam (convexHull ℝ (Set.range v0)) with hD
  obtain ⟨k, hk⟩ := sd_mesh_exists_k n D δ Metric.diam_nonneg hδ
  refine ⟨k, ?_⟩
  intro w hw
  have hbase : Finsupp.single v0 1 ∈ Finsupp.supported R R
      {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ |
        Metric.diam (convexHull ℝ (Set.range w)) ≤ D} :=
    Finsupp.single_mem_supported R 1 (le_refl D)
  have hiter := affine_sd_iter_diam (R := R) (E := Fin (n + 1) → ℝ) n D k
    (Finsupp.single v0 1) hbase
  rw [Finsupp.mem_support_iff, Finsupp.subtypeDomain_apply] at hw
  have hwsup : w.1 ∈ ((affine_sd (R := R) n ^ k) (Finsupp.single v0 1)).support :=
    Finsupp.mem_support_iff.mpr hw
  have hsub := (Finsupp.mem_supported R _).mp hiter (Finset.mem_coe.mpr hwsup)
  simp only [Set.mem_setOf_eq] at hsub
  exact le_trans hsub hk

/-- Any two points of a subset of the simplex with diameter at most `δ / 2` are within `δ`
of each other. -/
theorem dist_lt_delta_of_mem
    (n : ℕ) (δ : ℝ) (hδ : 0 < δ)
    (S : Set (Fin (n + 1) → ℝ))
    (hSsub : S ⊆ stdSimplex ℝ (Fin (n + 1)))
    (hdiam : Metric.diam S ≤ δ / 2) :
    ∀ x ∈ S, ∀ y ∈ S, dist x y < δ := by
  have hbdd : Bornology.IsBounded S :=
    (isCompact_stdSimplex ℝ (Fin (n + 1))).isBounded.subset hSsub
  intro x hx y hy
  calc dist x y ≤ Metric.diam S := Metric.dist_le_diam_of_mem hbdd hx hy
    _ ≤ δ / 2 := hdiam
    _ < δ := by linarith

/-- A subset `S` of the simplex with diameter at most `δ / 2` maps entirely into `A` or
entirely into `B`, given the pointwise `δ`-ball dichotomy `hL`. -/
theorem dichotomy_of_diam_le_half
    {X : TopCat.{0}} {A B : Set X}
    (n : ℕ) (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (δ : ℝ) (hδ : 0 < δ)
    (hL : ∀ x : stdSimplex ℝ (Fin (n + 1)),
      (∀ y : stdSimplex ℝ (Fin (n + 1)),
          dist (x : Fin (n + 1) → ℝ) (y : Fin (n + 1) → ℝ) < δ →
          X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ y ∈ A) ∨
      (∀ y : stdSimplex ℝ (Fin (n + 1)),
          dist (x : Fin (n + 1) → ℝ) (y : Fin (n + 1) → ℝ) < δ →
          X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ y ∈ B)) :
    ∀ S : Set (Fin (n + 1) → ℝ),
      S ⊆ stdSimplex ℝ (Fin (n + 1)) → Metric.diam S ≤ δ / 2 →
      (∀ p : stdSimplex ℝ (Fin (n + 1)), (p : Fin (n + 1) → ℝ) ∈ S →
          X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ p ∈ A) ∨
      (∀ p : stdSimplex ℝ (Fin (n + 1)), (p : Fin (n + 1) → ℝ) ∈ S →
          X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ p ∈ B) := by
  intro S hSsub hdiam
  have hdist : ∀ x ∈ S, ∀ y ∈ S, dist x y < δ :=
    dist_lt_delta_of_mem n δ hδ S hSsub hdiam
  rcases S.eq_empty_or_nonempty with hS | ⟨x₀, hx₀⟩
  · left; intro p hp; rw [hS] at hp; simp at hp
  · rcases hL ⟨x₀, hSsub hx₀⟩ with hA | hB
    · left
      intro p hp
      exact hA p (hdist x₀ hx₀ (p : Fin (n + 1) → ℝ) hp)
    · right
      intro p hp
      exact hB p (hdist x₀ hx₀ (p : Fin (n + 1) → ℝ) hp)

/-- Lebesgue-number theorem for the open cover `{σ⁻¹A, σ⁻¹B}` of the standard simplex: there
is `δ > 0` such that every subset of diameter at most `δ` maps entirely into `A` or entirely
into `B` under `σ`. -/
theorem singular_sd_lebesgue_delta
    {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ)
    (n : ℕ) (σ : (TopCat.toSSet.obj X) _⦋n⦌) :
    ∃ δ : ℝ, 0 < δ ∧ ∀ S : Set (Fin (n + 1) → ℝ),
      S ⊆ stdSimplex ℝ (Fin (n + 1)) → Metric.diam S ≤ δ →
      (∀ p : stdSimplex ℝ (Fin (n + 1)), (p : Fin (n + 1) → ℝ) ∈ S →
          X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ p ∈ A) ∨
      (∀ p : stdSimplex ℝ (Fin (n + 1)), (p : Fin (n + 1) → ℝ) ∈ S →
          X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ p ∈ B) := by
  obtain ⟨δ, hδ, hL⟩ := lebesgue_radius hA hB hAB n σ
  exact ⟨δ / 2, by positivity, dichotomy_of_diam_le_half n σ δ hδ hL⟩

/-- **Small simplices theorem**: for an open cover `{A, B}` of `X`, some iterate `k` of
barycentric subdivision of any singular simplex `σ` decomposes the fundamental chain into
pieces each mapping entirely into `A` or entirely into `B`. -/
theorem singular_sd_lebesgue_cover
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ)
    (n : ℕ) (σ : (TopCat.toSSet.obj X) _⦋n⦌) :
    ∃ k : ℕ, ∀ w ∈ (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (((affine_sd (R := R) n) ^ k)
            (Finsupp.single (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))).support,
      (∀ p : stdSimplex ℝ (Fin (n + 1)),
          (p : Fin (n + 1) → ℝ) ∈ convexHull ℝ (Set.range w.1) →
          X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ p ∈ A) ∨
      (∀ p : stdSimplex ℝ (Fin (n + 1)),
          (p : Fin (n + 1) → ℝ) ∈ convexHull ℝ (Set.range w.1) →
          X.toSSetObjEquiv (Opposite.op ⦋n⦌) σ p ∈ B) := by
  have h_leb := singular_sd_lebesgue_delta hA hB hAB n σ
  have h_mesh := singular_sd_iter_mesh_small (R := R) n
  obtain ⟨δ, hδ, hleb⟩ := h_leb
  obtain ⟨k, hk⟩ := h_mesh δ hδ
  refine ⟨k, fun w hw ↦ ?_⟩
  have hsub : convexHull ℝ (Set.range w.1) ⊆ stdSimplex ℝ (Fin (n + 1)) :=
    convexHull_min w.2 (convex_stdSimplex ℝ (Fin (n + 1)))
  exact hleb _ hsub (hk w hw)

/-- The composite `(singular_sd ^ k) ∘ Finsupp.lmapDomain (transport σ) ∘
Finsupp.subtypeDomain` is additive, so it distributes over the support decomposition
`c = ∑ v ∈ c.support, Finsupp.single v (c v)`. -/
theorem singular_sd_pow_transport_subtypeDomain_sum {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (c : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R) :
    ((singular_sd (R := R) (X := X) n) ^ k)
        (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) c))
      = ∑ v ∈ c.support,
          ((singular_sd (R := R) (X := X) n) ^ k)
            (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
              (Finsupp.subtypeDomain
                (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
                  Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single v (c v)))) := by
  classical
  set p : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ → Prop :=
    fun w ↦ Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)) with hp
  let G : ((affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R) →+ ((TopCat.toSSet.obj X) _⦋n⦌ →₀ R) :=
    (((singular_sd (R := R) (X := X) n) ^ k).toAddMonoidHom).comp
      (((Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))).toAddMonoidHom).comp
        (Finsupp.subtypeDomainAddMonoidHom (p := p)))
  have hG : ∀ x, G x = (singular_sd (R := R) (X := X) n ^ k)
      (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain p x)) := fun x ↦ rfl
  have key : G c = ∑ v ∈ c.support, G (Finsupp.single v (c v)) := by
    conv_lhs => rw [← Finsupp.sum_single c]
    exact map_sum G _ _
  simpa only [hG] using key

/-- The composite `Finsupp.lmapDomain (transport σ) ∘ Finsupp.subtypeDomain ∘
(affine_sd n) ^ k` is additive, so it distributes over the support decomposition
`c = ∑ v ∈ c.support, Finsupp.single v (c v)`. -/
theorem affine_sd_pow_transport_subtypeDomain_sum {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (c : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (((affine_sd (R := R) n) ^ k) c))
      = ∑ v ∈ c.support,
          Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k) (Finsupp.single v (c v)))) := by
  set F : ((affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R) →+ (TopCat.toSSet.obj X _⦋n⦌ →₀ R) :=
    (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))).toAddMonoidHom.comp
      ((Finsupp.subtypeDomainAddMonoidHom
          (p := fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))).comp
        ((affine_sd (R := R) n ^ k).toAddMonoidHom)) with hF
  change F c = ∑ v ∈ c.support, F (Finsupp.single v (c v))
  conv_lhs => rw [show c = ∑ v ∈ c.support, Finsupp.single v (c v) from (Finsupp.sum_single c).symm]
  rw [map_sum]

/-- Linear extension of a single-generator transport-naturality identity to every chain `c`
supported on the standard simplex, by decomposing `c` over its support and applying the
generator identity `h_gen` term by term. -/
theorem supported_linear_ext {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (h_gen : ∀ (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) (r : R),
      Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)) →
      ((singular_sd (R := R) (X := X) n) ^ k)
          (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single v r)))
        = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k) (Finsupp.single v r))))
    (c : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R)
    (hc : c ∈ Finsupp.supported R R
      {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ | Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))}) :
    ((singular_sd (R := R) (X := X) n) ^ k)
        (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) c))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ k) c)) := by
  classical
  have hlhs := singular_sd_pow_transport_subtypeDomain_sum (R := R) (X := X) n k σ c
  have hrhs := affine_sd_pow_transport_subtypeDomain_sum (R := R) (X := X) n k σ c
  rw [hlhs, hrhs]
  refine Finset.sum_congr rfl (fun v hv ↦ ?_)
  have hsub := (Finsupp.mem_supported (R := R) c).mp hc
  have hrange : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)) := hsub hv
  exact h_gen v (c v) hrange

/-- Naturality of the `k`-th power of singular subdivision under transport of a scalar
multiple of a generator `v`: it factors through transport along the singular simplex obtained
by transporting `v` itself along `σ`. -/
theorem singular_sd_pow_single_smul_transport_fund {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) (r : R)
    (hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)))
    (ih : ∀ (τ : (TopCat.toSSet.obj X) _⦋n⦌),
      ((singular_sd (R := R) (X := X) n) ^ k) (Finsupp.single τ 1)
        = Finsupp.lmapDomain R R ((singular_transport τ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k)
                (Finsupp.single (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)))) :
    ((singular_sd (R := R) (X := X) n) ^ k)
        (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single v r)))
      = r • Finsupp.lmapDomain R R
          ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
            (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ k)
              (Finsupp.single (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))) := by
  classical
  have h1 : Finsupp.subtypeDomain (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
        Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single v r)
      = Finsupp.single (⟨v, hv⟩ : {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ //
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))}) r := by
    ext ⟨a, ha⟩
    rw [Finsupp.subtypeDomain_apply]
    by_cases h : a = v
    · subst h
      erw [Finsupp.single_eq_same, Finsupp.single_eq_same]
    · erw [Finsupp.single_eq_of_ne h,
          Finsupp.single_eq_of_ne (fun heq => h (congrArg Subtype.val heq))]
  rw [h1, Finsupp.lmapDomain_apply]
  erw [Finsupp.mapDomain_single]
  rw [← Finsupp.smul_single_one, map_smul]
  congr 1
  exact ih _

/-- The scalar `r` factors out of the composite of `(affine_sd n) ^ k`,
`Finsupp.subtypeDomain`, and transport along `σ`, applied to `Finsupp.single v r`. -/
theorem transport_scalar_factor {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) (r : R) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (((affine_sd (R := R) n) ^ k) (Finsupp.single v r)))
      = r • Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ k) (Finsupp.single v (1 : R)))) := by
  set P : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ → Prop :=
    fun w ↦ Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)) with hP
  have hsub : ∀ x : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R,
      Finsupp.subtypeDomain P (r • x) = r • Finsupp.subtypeDomain P x := by
    intro x
    ext a
    simp [Finsupp.subtypeDomain_apply, Finsupp.smul_apply]
  have h1 : (Finsupp.single v r : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R)
      = r • Finsupp.single v (1 : R) := by
    rw [Finsupp.smul_single, smul_eq_mul, mul_one]
  rw [h1, map_smul, hsub]
  exact map_smul (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌)))
    r (Finsupp.subtypeDomain P ((affine_sd (R := R) n ^ k) (Finsupp.single v 1)))

/-- `(affine_sd n) ^ k` maps the fundamental generator into the subcomplex of tuples with
range contained in the standard simplex, for every iteration count `k`. -/
theorem sd_pow_fund_supported {R : Type} [Ring R] (n k : ℕ) :
    ((affine_sd (R := R) n) ^ k)
        (Finsupp.single (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)
      ∈ Finsupp.supported R R
          {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ |
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))} := by
  induction k with
  | zero =>
      rw [pow_zero]
      apply Finsupp.single_mem_supported
      simp only [Set.mem_setOf_eq, Set.range_subset_iff]
      intro i
      exact single_mem_stdSimplex ℝ i
  | succ k ih =>
      rw [pow_succ']
      exact affine_sd_supported (convex_stdSimplex ℝ (Fin (n + 1))) n _ ih

/-- Pushing the fundamental generator forward along `Fintype.linearCombination ℝ v` produces
the generator `Finsupp.single v 1`. -/
theorem linear_comb_pushforward_single_fund {R : Type} [Ring R] (n : ℕ)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) :
    Finsupp.lmapDomain R R
        (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ ↦
          (⇑(Fintype.linearCombination ℝ v) ∘ w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌))
        (Finsupp.single (fun i ↦ (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)
    = Finsupp.single v (1 : R) := by
  rw [Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
  congr 1
  funext i
  simp [Fintype.linearCombination_apply_single]

/-- Naturality of the `k`-th power of barycentric subdivision `affine_sd n` under
postcomposition with `Finsupp.lmapDomain (g ∘ ·)` for a linear map `g`. -/
theorem sd_pow_map_naturality {R : Type} [Ring R] {E F : Type}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n k : ℕ) :
    ((affine_sd (R := R) n) ^ k) ∘ₗ
        Finsupp.lmapDomain R R
          (fun w : (affine_sset E) _⦋n⦌ ↦ (⇑g ∘ w : (affine_sset F) _⦋n⦌))
      = Finsupp.lmapDomain R R
          (fun w : (affine_sset E) _⦋n⦌ ↦ (⇑g ∘ w : (affine_sset F) _⦋n⦌))
          ∘ₗ ((affine_sd (R := R) n) ^ k) :=
  Module.End.commute_pow_left_of_commute (affine_sd_map g n) k

end Library.AlgebraicTopology.MayerVietoris.SubdivisionMeshBound
