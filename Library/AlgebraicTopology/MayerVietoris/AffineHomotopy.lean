import Mathlib.AlgebraicTopology.SimplicialSet.TopAdj
import Mathlib.Analysis.InnerProductSpace.Basic
import Library.AlgebraicTopology.MayerVietoris.ShortExactComplex

/-!
# Affine chain homotopy for barycentric subdivision

This file develops the affine (straight-line) chain homotopy `T = affine_ht` between
the identity and the barycentric subdivision operator `S = affine_sd` on chains of
affine simplices, following Hatcher, *Algebraic Topology*, §2.1. It establishes the
two defining Hatcher identities

* the chain-map property `∂ ∘ S = S ∘ ∂` (`affine_sd_boundary`), and
* the chain-homotopy identity `∂T + T∂ = id − S` (`affine_ht_boundary`),

together with naturality of `S` and `T` under postcomposition by an `ℝ`-linear map
(`affine_sd_map`, `affine_ht_map`), and preservation of "support in a convex set `s`"
by `S`, `T` and the boundary operator (`affine_sd_supported`, `affine_ht_supported`,
`affine_boundary_supported`).

The second half of the file transports this affine machinery to singular chains of
a topological space `X` via the *singular transport* morphism `singular_transport`,
which realizes an affine chain on the standard simplex along a singular simplex
`σ : Δⁿ → X`. This produces the singular subdivision operator `singular_sd` and the
singular homotopy `singular_ht`, the small-simplices engine of the Mayer–Vietoris
sequence.

## Main definitions

* `affine_ht`: the degree-raising affine cone homotopy `T`.
* `affine_subcomplex_of_set`: the subcomplex of `affine_sset E` supported on tuples
  valued in a set `s`.
* `affine_subcomplex_realization`: the realization morphism corestricted to a convex
  set `s`.
* `singular_transport`: per-generator transport of affine chains along a singular
  simplex.
* `singular_sd`, `singular_ht`: the singular-level subdivision operator and homotopy.

## Main statements

* `affine_sd_boundary`, `affine_ht_boundary`: Hatcher's chain-map and
  chain-homotopy identities for `affine_sd` and `affine_ht`.
* `affine_sd_map`, `affine_ht_map`: naturality under postcomposition with a linear
  map.
* `affine_sd_supported`, `affine_ht_supported`: preservation of support in a convex
  set.

## References

* A. Hatcher, *Algebraic Topology*, §2.1.
-/

universe u

open CategoryTheory Simplicial
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Simplicial
open Simplicial CategoryTheory
open scoped Simplicial

namespace Library.AlgebraicTopology.MayerVietoris.AffineHomotopy

-- Forward rationale: Hatcher §2.1's cone chain homotopy `T` on affine (LC) chains,
-- companion of the landed `affine_sd`, raising degree by one. Degree 0 is the ZERO
-- map; on a degree-(n+1) generator `v : Fin (n+2) → E` with barycenter
-- `b = centroid ℝ v`, `T(v) = b · (v − T_n(∂ v))` via the `affine_cone` apex
-- operator, with `∂` the same alternating boundary sum used inside `affine_sd`'s
-- recursion. Built via `Finsupp.linearCombination` to stay linear over a
-- NONcommutative ring `R` (`Finsupp.lsum` would demand `SMulCommClass`). This is the
-- homotopy on which Hatcher's identity `∂T + T∂ = S − id` (the small-simplices
-- quasi-iso for Mayer–Vietoris) is built. The two defining equations
-- (`affine_ht 0 = 0`; the generator recursion) land as separate later bricks.
noncomputable def affine_ht {R : Type u} [Ring R] {E : Type u} [AddCommGroup E] [Module ℝ E]
    (n : ℕ) : ((affine_sset E) _⦋n⦌ →₀ R) →ₗ[R] ((affine_sset E) _⦋n + 1⦌ →₀ R) := by
  induction n with
  | zero => exact 0
  | succ n ih =>
      exact Finsupp.linearCombination R (fun v =>
        affine_cone (R := R) (Finset.univ.centroid ℝ v) (n + 1)
          (Finsupp.single v 1 - ih ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
            • Finsupp.lmapDomain R R ((affine_sset E).δ i)) (Finsupp.single v 1))))

-- Forward rationale: the degree-0 defining equation of the barycentric subdivision
-- operator `affine_sd`. Its `L_affine_sd.lean` header promised BOTH defining equations
-- as separate bricks, but `affine_sd` is built by `induction` on `n`, so its zero case
-- is not transparently defeq downstream; this brick pins `affine_sd 0 = id`. The chain-map
-- identity, the homotopy `∂T + T∂ = id − S`, and the diameter estimate all evaluate
-- `affine_sd` at degree 0 through this equation.
theorem affine_sd_zero {R : Type u} [Ring R] {E : Type u} [AddCommGroup E] [Module ℝ E] :
    (@affine_sd R _ E _ _ 0) = LinearMap.id := by trivial

-- Base case P(0) of the chain-map property `∂ ∘ S = S ∘ ∂` for barycentric
-- subdivision `affine_sd`. Since `affine_sd 0 = id`, the RHS is just `∂`. Reduce
-- to generators `single v 1` via `Finsupp.lhom_ext'`; there `affine_sd 1 (single v 1)`
-- unfolds (via `affine_sd_succ_single` + `affine_sd_zero`) to `cone_b (∂ (single v 1))`
-- with apex `b = centroid v`. The cone boundary identity `affine_cone_zero_boundary`
-- (`∂ ∘ cone_b = id - const_b`) gives `∂ (single v 1) - const_b (∂ (single v 1))`, and the
-- augmentation term `const_b (∂ (single v 1))` vanishes since the boundary of a 1-simplex
-- has coefficient sum `1 - 1 = 0`.
theorem affine_sd_chain_map_base {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] :
    (∑ i : Fin (0 + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        ∘ₗ affine_sd (R := R) (0 + 1)
      = affine_sd (R := R) 0 ∘ₗ
          (∑ i : Fin (0 + 2),
            (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i)) := by
  rw [affine_sd_zero, LinearMap.id_comp]
  apply Finsupp.lhom_ext'
  intro v
  apply LinearMap.ext
  intro r
  simp only [LinearMap.comp_apply, Finsupp.lsingle_apply]
  rw [show (Finsupp.single v r) = r • Finsupp.single v (1 : R) by
        rw [Finsupp.smul_single, smul_eq_mul, mul_one]]
  simp only [map_smul]
  congr 1
  rw [affine_sd_succ_single]
  simp only [affine_sd_zero, LinearMap.id_coe, id_eq]
  rw [← LinearMap.comp_apply, affine_cone_zero_boundary]
  erw [LinearMap.sub_apply, LinearMap.id_apply, sub_eq_self]
  have haug : ∀ b : E,
      Finsupp.lmapDomain R R (fun (_ : (affine_sset E) _⦋0⦌) => (fun (_ : Fin 1) => b))
        ((∑ i : Fin 2, (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
          (Finsupp.single v 1)) = 0 := by
    intro b
    simp only [LinearMap.sum_apply, LinearMap.smul_apply, map_sum, map_zsmul,
      Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
    rw [Fin.sum_univ_two]
    simp
  exact haug _

-- Inductive step of `∂ ∘ S = S ∘ ∂` (Hatcher §2.1), computed on generators.
-- Reduce to a generator `single v 1` (`lhom_ext'` + `ext_ring`); expand
-- `S(v) = b·S(∂ v)` (`affine_sd_succ_single`), apply the cone-boundary identity
-- `∂(b·w) = w − b·(∂w)` (`affine_cone_boundary`); the correction term vanishes since
-- `∂ ∘ S ∘ ∂ = 0` (ih + `finsupp_boundary_sq_zero`).
theorem affine_sd_chain_map_step {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] (n : ℕ)
    (ih : (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        ∘ₗ affine_sd (R := R) (n + 1)
      = affine_sd (R := R) n ∘ₗ
          (∑ i : Fin (n + 2),
            (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))) :
    (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        ∘ₗ affine_sd (R := R) (n + 2)
      = affine_sd (R := R) (n + 1) ∘ₗ
          (∑ i : Fin (n + 3),
            (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i)) := by
  apply Finsupp.lhom_ext'
  intro v
  apply LinearMap.ext_ring
  simp only [LinearMap.comp_apply, Finsupp.lsingle_apply]
  have hss : affine_sd (R := R) (n + 2) (Finsupp.single v 1)
      = affine_cone (R := R) (Finset.univ.centroid ℝ v) (n + 1)
          (affine_sd (R := R) (n + 1)
            ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
              (Finsupp.single v 1))) := affine_sd_succ_single (R := R) (n + 1) v
  rw [hss, ← LinearMap.comp_apply, affine_cone_boundary (R := R) (Finset.univ.centroid ℝ v) n]
  simp only [LinearMap.sub_apply, LinearMap.id_apply, LinearMap.comp_apply]
  have hsq : (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
      ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        (Finsupp.single v 1)) = 0 := by
    rw [← LinearMap.comp_apply, finsupp_boundary_sq_zero]
    simp
  have hzero :
      (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        (affine_sd (R := R) (n + 1)
          ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
            (Finsupp.single v 1))) = 0 := by
    rw [← LinearMap.comp_apply, ih, LinearMap.comp_apply, hsq, map_zero]
  rw [hzero, map_zero, sub_zero]

-- Chain-map property `∂ ∘ S = S ∘ ∂` of the barycentric subdivision `affine_sd`,
-- proven by induction on `n` (Hatcher §2.1).
-- `affine_sd_chain_map_base` handles `P(0)` (degree-0 base case, `affine_sd 0 = id`);
-- `affine_sd_chain_map_step` handles the inductive step `P(n) → P(n+1)` (compute on
-- generators via `affine_sd_succ_single`, `affine_cone_boundary`, and `∂∂ = 0`).
theorem affine_sd_boundary {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] (n : ℕ) :
    (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        ∘ₗ affine_sd (R := R) (n + 1)
      = affine_sd (R := R) n ∘ₗ
          (∑ i : Fin (n + 2),
            (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i)) := by
  induction n with
  | zero => exact affine_sd_chain_map_base
  | succ n ih => exact affine_sd_chain_map_step n ih

-- Forward rationale: The cone homotopy `affine_ht` (proofs/L_affine_ht.lean) is
-- built by `induction`, so its zero branch is not transparently defeq downstream.
-- This brick pins the base-degree defining equation `affine_ht 0 = 0` (mirroring
-- the sibling `affine_sd_zero`). The homotopy identity `∂T + T∂ = id − S` uses it
-- to kill the `T∘∂` term at base degree.
theorem affine_ht_zero {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] :
    (@affine_ht R _ E _ _ 0) = 0 := by trivial

-- Forward rationale: the defining generator recursion of the landed cone homotopy
-- `affine_ht` (`proofs/L_affine_ht.lean`), whose brick deferred it (one decl per
-- brick). On a degree-(n+1) generator `v : Fin (n+2) → E` with barycenter
-- `b = centroid ℝ v`, `T(v) = b · (v − T_n(∂ v))` via `affine_cone`, with `∂` the
-- EXACT alternating boundary sum used inside `affine_ht`'s recursion (matching
-- `affine_sd_succ_single`). Every downstream evaluation of `T` on generators
-- (Hatcher's homotopy identity `∂T + T∂ = S − id`, the iterated-subdivision
-- telescope) computes `affine_ht` through this single equation.
theorem affine_ht_succ_single {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] (n : ℕ) (v : Fin (n + 2) → E) :
    affine_ht (R := R) (n + 1) (Finsupp.single v 1)
      = affine_cone (R := R) (Finset.univ.centroid ℝ v) (n + 1)
          ((Finsupp.single v 1 : (affine_sset E) _⦋n + 1⦌ →₀ R) - affine_ht (R := R) n
            ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((affine_sset E).δ i)) (Finsupp.single v 1))) := by
  simp [affine_ht]

-- affine_ht_boundary_base: the `n = 0` case of Hatcher's chain-homotopy identity
-- `∂T + T∂ = id − S`. `affine_ht 0 = 0` kills the `T∂` term; on the remaining
-- generator `single v 1`, unfold `T` (`affine_ht_succ_single`) to a single
-- `affine_cone` term and push the boundary sum through it via `affine_cone_boundary`,
-- matching the RHS produced by unfolding `S` via `affine_sd_succ_single`/`affine_sd_zero`.
theorem affine_ht_boundary_base {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] :
    (∑ i : Fin (0 + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        ∘ₗ affine_ht (R := R) (0 + 1)
      + affine_ht (R := R) 0
        ∘ₗ (∑ i : Fin (0 + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
      = LinearMap.id - affine_sd (R := R) (0 + 1) := by
  rw [affine_ht_zero, LinearMap.zero_comp, add_zero]
  apply Finsupp.lhom_ext'
  intro v
  apply LinearMap.ext_ring
  simp only [LinearMap.comp_apply, LinearMap.sub_apply, LinearMap.id_apply, Finsupp.lsingle_apply]
  rw [affine_ht_succ_single, affine_ht_zero]
  simp only [LinearMap.zero_apply, sub_zero]
  have hcb := LinearMap.congr_fun
    (affine_cone_boundary (R := R) (Finset.univ.centroid ℝ v) 0) (Finsupp.single v 1)
  have hsd := affine_sd_succ_single (R := R) 0 v
  simp only [LinearMap.comp_apply, LinearMap.sub_apply, LinearMap.id_apply] at hcb
  rw [hsd, affine_sd_zero, LinearMap.id_apply]
  rw [hcb]

-- Inductive step of the chain homotopy identity `∂T + T∂ = id − S` (Hatcher §2.1),
-- computed on a generator `single v 1`. Reduce to the generator (`lhom_ext'` +
-- `ext_ring`); expand `T(v) = b·(v − T(∂v))` (`affine_ht_succ_single`) and apply the
-- cone-boundary identity `∂(b·w) = w − b·(∂w)` (`affine_cone_boundary`). The key step
-- `∂w = S(∂v)` follows from the inductive hypothesis applied to `∂v` together with
-- `∂∂ = 0` (`finsupp_boundary_sq_zero`); the RHS matches via `affine_sd_succ_single`,
-- and the residual `−T(∂v) + T(∂v)` cancels (`abel`).
theorem affine_ht_boundary_step {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] (n : ℕ)
    (ih : (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        ∘ₗ affine_ht (R := R) (n + 1)
      + affine_ht (R := R) n
        ∘ₗ (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
      = LinearMap.id - affine_sd (R := R) (n + 1)) :
    (∑ i : Fin (n + 4), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        ∘ₗ affine_ht (R := R) (n + 2)
      + affine_ht (R := R) (n + 1)
        ∘ₗ (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
      = LinearMap.id - affine_sd (R := R) (n + 2) := by
  apply Finsupp.lhom_ext'
  intro v
  apply LinearMap.ext_ring
  simp only [LinearMap.add_apply, LinearMap.comp_apply, Finsupp.lsingle_apply]
  rw [affine_ht_succ_single (R := R) (n + 1) v]
  rw [← LinearMap.comp_apply, affine_cone_boundary (R := R) (Finset.univ.centroid ℝ v) (n + 1)]
  simp only [LinearMap.sub_apply, LinearMap.id_apply, LinearMap.comp_apply]
  -- ∂∂ = 0 on the generator
  have hsq : (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
      ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        (Finsupp.single v 1)) = 0 := by
    rw [← LinearMap.comp_apply, finsupp_boundary_sq_zero]
    simp
  -- IH applied to x = ∂ (single v 1)
  have hih := LinearMap.congr_fun ih
    ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
      (Finsupp.single v 1))
  simp only [LinearMap.add_apply, LinearMap.comp_apply, LinearMap.sub_apply,
    LinearMap.id_apply] at hih
  rw [hsq, map_zero, add_zero] at hih
  -- ∂ w = S(n+1) (∂ single v 1)
  have hkey : (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
      ((Finsupp.single v 1 : (affine_sset E) _⦋n + 2⦌ →₀ R) - affine_ht (R := R) (n + 1)
        ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
          (Finsupp.single v 1)))
      = affine_sd (R := R) (n + 1)
        ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
          (Finsupp.single v 1)) := by
    rw [map_sub, hih]
    abel
  rw [hkey, affine_sd_succ_single (R := R) (n + 1) v]
  abel

-- Hatcher §2.1 chain-homotopy identity `∂T + T∂ = id − S` on affine (LC) chains,
-- by induction on the degree `n` (same split as the sibling `affine_sd_boundary`).
-- `affine_ht_boundary_base` : the `n = 0` case (T₀ = 0 kills the `T∂` term, reduce
--   on the degree-1 generator via the cone-boundary identity).
-- `affine_ht_boundary_step` : the inductive step `P(n) → P(n+1)`, computed on a
--   generator via `affine_ht_succ_single` / `affine_cone_boundary` / `∂∂ = 0`.
theorem affine_ht_boundary {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] (n : ℕ) :
    (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
        ∘ₗ affine_ht (R := R) (n + 1)
      + affine_ht (R := R) n
        ∘ₗ (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) • Finsupp.lmapDomain R R ((affine_sset E).δ i))
      = LinearMap.id - affine_sd (R := R) (n + 1) := by
  induction n with
  | zero => exact affine_ht_boundary_base
  | succ n ih => exact affine_ht_boundary_step n ih

theorem affine_ht_map_base {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) :
    affine_ht (R := R) 0 ∘ₗ
        Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋0⦌ => (⇑g ∘ v : (affine_sset F) _⦋0⦌))
      = Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋0 + 1⦌ => (⇑g ∘ v : (affine_sset F) _⦋0 + 1⦌))
          ∘ₗ affine_ht (R := R) 0 := by noncomm_ring

theorem affine_sd_map_base {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) :
    affine_sd (R := R) 0 ∘ₗ
        Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋0⦌ => (⇑g ∘ v : (affine_sset F) _⦋0⦌))
      = Finsupp.lmapDomain R R (fun v : (affine_sset E) _⦋0⦌ => (⇑g ∘ v : (affine_sset F) _⦋0⦌))
          ∘ₗ affine_sd (R := R) 0 := by noncomm_ring

-- centroid_map_naturality: an ℝ-linear map commutes with centroids, via
-- `Finset.map_affineCombination` applied to `g.toAffineMap` (a linear map is an
-- affine map fixing the origin), with the centroid weights summing to 1.
theorem centroid_map_naturality {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n : ℕ) :
    ∀ (v : Fin (n + 2) → E),
      g (Finset.univ.centroid ℝ v) = Finset.univ.centroid ℝ (⇑g ∘ v) := by
  intro v
  rw [Finset.centroid_def, Finset.centroid_def]
  have hw : ∑ i, (Finset.univ : Finset (Fin (n + 2))).centroidWeights ℝ i = 1 :=
    Finset.univ.sum_centroidWeights_eq_one_of_card_eq_add_one ℝ
      (n := n + 1) (by simp)
  exact Finset.univ.map_affineCombination v (Finset.univ.centroidWeights ℝ) hw g.toAffineMap

-- cone_map_naturality: naturality of the cone operator `affine_cone` under
-- postcomposition with a linear map `g`, via `Fin.comp_cons` + `Finsupp.lmapDomain_comp`.
-- Reduces `lmapDomain(g∘·) ∘ₗ lmapDomain(cons b·) = lmapDomain(cons(g b)·) ∘ₗ lmapDomain(g∘·)`
-- to the pointwise vertex-tuple identity `g ∘ Fin.cons b v = Fin.cons (g b) (g ∘ v)`.
theorem cone_map_naturality {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n : ℕ) :
    ∀ (b : E) (x : ((affine_sset E) _⦋n⦌ →₀ R)),
      Finsupp.lmapDomain R R
          (fun w : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1⦌))
          (affine_cone (R := R) b n x)
        = affine_cone (R := R) (g b) n
            (Finsupp.lmapDomain R R
              (fun w : (affine_sset E) _⦋n⦌ => (⇑g ∘ w : (affine_sset F) _⦋n⦌)) x) := by
  intro b x
  simp only [affine_cone]
  have key : (Finsupp.lmapDomain R R
        (fun w : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1⦌))) ∘ₗ
      (Finsupp.lmapDomain R R (fun v : (affine_sset E) _⦋n⦌ => Fin.cons b v))
    = (Finsupp.lmapDomain R R (fun v : (affine_sset F) _⦋n⦌ => Fin.cons (g b) v)) ∘ₗ
      (Finsupp.lmapDomain R R
        (fun w : (affine_sset E) _⦋n⦌ => (⇑g ∘ w : (affine_sset F) _⦋n⦌))) := by
    rw [← Finsupp.lmapDomain_comp, ← Finsupp.lmapDomain_comp]
    congr 1
    funext v
    exact Fin.comp_cons (⇑g) b v
  exact LinearMap.congr_fun key x

-- face_lmapdomain_naturality: per-face naturality of lmapDomain(g∘·) against affine_sset.δ
-- `lmapDomain_comp` turns both composites into `lmapDomain (f∘g)`, reducing to the pointwise
-- function equality `(g∘·)∘δᵢ = δᵢ∘(g∘·)`, which `congr 1` closes by defeq (δᵢ w = w∘succAbove i).
theorem face_lmapdomain_naturality {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n : ℕ) :
    ∀ (i : Fin (n + 2)),
      Finsupp.lmapDomain R R (fun w : (affine_sset E) _⦋n⦌ => (⇑g ∘ w : (affine_sset F) _⦋n⦌))
            ∘ₗ Finsupp.lmapDomain R R ((affine_sset E).δ i)
        = Finsupp.lmapDomain R R ((affine_sset F).δ i)
            ∘ₗ Finsupp.lmapDomain R R
                (fun w : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1⦌)) := by
  intro i
  rw [← Finsupp.lmapDomain_comp, ← Finsupp.lmapDomain_comp]
  congr 1

theorem boundary_map_naturality {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n : ℕ) :
    ∀ (x : ((affine_sset E) _⦋n + 1⦌ →₀ R)),
      Finsupp.lmapDomain R R (fun w : (affine_sset E) _⦋n⦌ => (⇑g ∘ w : (affine_sset F) _⦋n⦌))
          ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
            • Finsupp.lmapDomain R R ((affine_sset E).δ i)) x)
        = (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
            • Finsupp.lmapDomain R R ((affine_sset F).δ i))
            (Finsupp.lmapDomain R R
              (fun w : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1⦌)) x) := by
  have hface := face_lmapdomain_naturality (R := R) g n
  intro x
  rw [LinearMap.sum_apply, map_sum, LinearMap.sum_apply]
  refine Finset.sum_congr rfl (fun i _ => ?_)
  rw [LinearMap.smul_apply, map_zsmul, LinearMap.smul_apply]
  congr 1
  rw [← LinearMap.comp_apply, hface i]
  rfl

-- Naturality of barycentric subdivision `affine_sd` under postcomposition with an
-- ℝ-linear map g (inductive step). Reduce to a generator `single v 1` via
-- `lhom_ext' + ext_ring`, expand both sides with `affine_sd_succ_single`, then
-- rewrite the RHS to the LHS through three pointwise naturality facts —
-- `cone_map_naturality`, `centroid_map_naturality`, `boundary_map_naturality` —
-- plus the inductive hypothesis `ih`.
theorem affine_sd_map_step {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n : ℕ)
    (ih : affine_sd (R := R) n ∘ₗ
        Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n⦌ => (⇑g ∘ v : (affine_sset F) _⦋n⦌))
      = Finsupp.lmapDomain R R (fun v : (affine_sset E) _⦋n⦌ => (⇑g ∘ v : (affine_sset F) _⦋n⦌))
          ∘ₗ affine_sd (R := R) n) :
    affine_sd (R := R) (n + 1) ∘ₗ
        Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ v : (affine_sset F) _⦋n + 1⦌))
      = Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ v : (affine_sset F) _⦋n + 1⦌))
          ∘ₗ affine_sd (R := R) (n + 1) := by
  have h_cone := cone_map_naturality (R := R) g n
  have h_centroid := centroid_map_naturality g n
  have h_boundary := boundary_map_naturality (R := R) g n
  apply Finsupp.lhom_ext'
  intro v
  apply LinearMap.ext_ring
  have hm : (Finsupp.lmapDomain R R
        (fun w : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1⦌)))
        (Finsupp.single v 1) = Finsupp.single (⇑g ∘ v) 1 := by
    rw [Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
  have ih_app : ∀ z, affine_sd (R := R) n
        (Finsupp.lmapDomain R R (fun w : (affine_sset E) _⦋n⦌ => (⇑g ∘ w : (affine_sset F) _⦋n⦌)) z)
      = Finsupp.lmapDomain R R (fun w : (affine_sset E) _⦋n⦌ => (⇑g ∘ w : (affine_sset F) _⦋n⦌))
          (affine_sd (R := R) n z) := fun z => DFunLike.congr_fun ih z
  simp only [LinearMap.comp_apply, Finsupp.lsingle_apply]
  erw [hm, affine_sd_succ_single]
  have hrhs : ((Finsupp.lmapDomain R R
        (fun w : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1⦌)))
        ∘ₗ affine_sd (R := R) (n + 1)) (Finsupp.single v 1)
      = (Finsupp.lmapDomain R R
        (fun w : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1⦌)))
        (affine_sd (R := R) (n + 1) (Finsupp.single v 1)) := rfl
  erw [hrhs, affine_sd_succ_single]
  rw [h_cone, h_centroid, ← ih_app, h_boundary]
  erw [hm]
  rfl

-- Naturality of barycentric subdivision `affine_sd` under postcomposition with an
-- ℝ-linear map g, by induction on n. Base case `affine_sd_map_base` (degree 0,
-- affine_sd 0 = id); inductive step `affine_sd_map_step` (recursion via
-- affine_sd_succ_single, cone naturality, centroid naturality, and the IH).
theorem affine_sd_map {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n : ℕ) :
    affine_sd (R := R) n ∘ₗ
        Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n⦌ => (⇑g ∘ v : (affine_sset F) _⦋n⦌))
      = Finsupp.lmapDomain R R (fun v : (affine_sset E) _⦋n⦌ => (⇑g ∘ v : (affine_sset F) _⦋n⦌))
          ∘ₗ affine_sd (R := R) n := by
  induction n with
  | zero => exact affine_sd_map_base g
  | succ n ih => exact affine_sd_map_step g n ih

-- The alternating-sum boundary map commutes with the pushforward `g ∘ ·`.
-- Distribute both boundary sums over application (`sum_apply`/`smul_apply`) and
-- push the pushforward linear map through the RHS sum (`map_sum`/`map_zsmul`),
-- reducing to the per-face naturality; each face term closes by the proved
-- sibling `face_lmapdomain_naturality` applied at the generator `c`.
theorem affine_boundary_map_naturality {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n : ℕ)
    (c : (affine_sset E) _⦋n + 1⦌ →₀ R) :
    (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
        • Finsupp.lmapDomain R R ((affine_sset F).δ i))
        (Finsupp.lmapDomain R R
          (fun w : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1⦌)) c)
      = Finsupp.lmapDomain R R
          (fun w : (affine_sset E) _⦋n⦌ => (⇑g ∘ w : (affine_sset F) _⦋n⦌))
          ((∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
              • Finsupp.lmapDomain R R ((affine_sset E).δ i)) c) :=
    (boundary_map_naturality g n c).symm

-- affine_cone_map_naturality: instance of `cone_map_naturality` at degree `n+1`.
-- The goal statement is exactly `cone_map_naturality g (n+1) b c` unfolded.
theorem affine_cone_map_naturality {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n : ℕ) (b : E)
    (c : (affine_sset E) _⦋n + 1⦌ →₀ R) :
    Finsupp.lmapDomain R R
        (fun w : (affine_sset E) _⦋n + 1 + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1 + 1⦌))
        (affine_cone (R := R) b (n + 1) c)
      = affine_cone (R := R) (g b) (n + 1)
          (Finsupp.lmapDomain R R
            (fun w : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1⦌)) c) :=
    cone_map_naturality g (n + 1) b c

-- Generator step of `affine_ht` naturality under postcomposition with `g`.
-- Expand both cone homotopies via `affine_ht_succ_single`, push `g` through the
-- apex with `centroid_map_naturality`, then move the pushforward inside the cone
-- (`affine_cone_map_naturality`), split the `single - affine_ht (∂ …)` argument,
-- and close the boundary term by threading the IH through the pushforward and
-- the boundary naturality `affine_boundary_map_naturality`.
theorem affine_ht_map_step_gen {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n : ℕ)
    (ih : affine_ht (R := R) n ∘ₗ
        Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n⦌ => (⇑g ∘ v : (affine_sset F) _⦋n⦌))
      = Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ v : (affine_sset F) _⦋n + 1⦌))
          ∘ₗ affine_ht (R := R) n)
    (v : (affine_sset E) _⦋n + 1⦌) :
    affine_ht (R := R) (n + 1)
        (Finsupp.single (⇑g ∘ v : (affine_sset F) _⦋n + 1⦌) 1)
      = Finsupp.lmapDomain R R
          (fun w : (affine_sset E) _⦋n + 1 + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1 + 1⦌))
          (affine_ht (R := R) (n + 1) (Finsupp.single v 1)) := by
  rw [affine_ht_succ_single, affine_ht_succ_single, ← centroid_map_naturality g n v]
  -- RHS: move pushforward g inside the cone via cone naturality
  rw [affine_cone_map_naturality g n]
  congr 1
  rw [map_sub]
  congr 1
  · rw [Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
    rfl
  · -- `affine_ht n` on the boundary, threaded through the IH and boundary naturality
    have kih : ∀ x : (affine_sset E) _⦋n⦌ →₀ R,
        affine_ht (R := R) n
            (Finsupp.lmapDomain R R
              (fun w : (affine_sset E) _⦋n⦌ => (⇑g ∘ w : (affine_sset F) _⦋n⦌)) x)
          = Finsupp.lmapDomain R R
              (fun w : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ w : (affine_sset F) _⦋n + 1⦌))
              (affine_ht (R := R) n x) :=
      fun x => LinearMap.congr_fun ih x
    rw [← kih]
    congr 1
    rw [← affine_boundary_map_naturality g n]
    congr 1
    rw [Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
    rfl

-- Inductive step of the naturality of the cone chain homotopy `affine_ht` under
-- postcomposition with an ℝ-linear map `g`. Reduce the linear-map equation to a
-- single generator `single v 1` (`Finsupp.lhom_ext'` + `LinearMap.ext_ring`);
-- `simp` normalizes the pushforward `G (single v 1) = single (g ∘ v) 1`, leaving the
-- generator-level identity `affine_ht_map_step_gen` (which discharges the cone /
-- centroid / boundary naturality of `g` against `affine_ht_succ_single` and the IH).
theorem affine_ht_map_step {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n : ℕ)
    (ih : affine_ht (R := R) n ∘ₗ
        Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n⦌ => (⇑g ∘ v : (affine_sset F) _⦋n⦌))
      = Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ v : (affine_sset F) _⦋n + 1⦌))
          ∘ₗ affine_ht (R := R) n) :
    affine_ht (R := R) (n + 1) ∘ₗ
        Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ v : (affine_sset F) _⦋n + 1⦌))
      = Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n + 1 + 1⦌ => (⇑g ∘ v : (affine_sset F) _⦋n + 1 + 1⦌))
          ∘ₗ affine_ht (R := R) (n + 1) := by
  apply Finsupp.lhom_ext'
  intro v
  apply LinearMap.ext_ring
  simp only [LinearMap.comp_apply, Finsupp.lsingle_apply, Finsupp.lmapDomain_apply,
    Finsupp.mapDomain_single]
  exact affine_ht_map_step_gen (R := R) g n ih v

-- Naturality of the cone chain homotopy `affine_ht` under postcomposition with an
-- ℝ-linear map `g : E →ₗ[ℝ] F`, by induction on the degree `n` (same base/step split
-- as the sibling `affine_ht_boundary`).
-- `affine_ht_map_base` : the `n = 0` case (`affine_ht 0 = 0`, both sides vanish).
-- `affine_ht_map_step` : the inductive step `P(n) → P(n+1)`, computed on a generator via
--   `affine_ht_succ_single`, centroid/cone/boundary naturality of `g`, and the IH.
theorem affine_ht_map {R : Type u} [Ring R] {E F : Type u}
    [AddCommGroup E] [Module ℝ E] [AddCommGroup F] [Module ℝ F]
    (g : E →ₗ[ℝ] F) (n : ℕ) :
    affine_ht (R := R) n ∘ₗ
        Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n⦌ => (⇑g ∘ v : (affine_sset F) _⦋n⦌))
      = Finsupp.lmapDomain R R
          (fun v : (affine_sset E) _⦋n + 1⦌ => (⇑g ∘ v : (affine_sset F) _⦋n + 1⦌))
          ∘ₗ affine_ht (R := R) n := by
  induction n with
  | zero => exact affine_ht_map_base (R := R) g
  | succ n ih => exact affine_ht_map_step (R := R) g n ih

-- Forward rationale: The affine-side mirror of `s17856`
-- (`singular_subcomplex_of_set`): the subcomplex of `affine_sset E` whose
-- `n`-simplices are the vertex tuples valued in a given set `s`. Since
-- `(affine_sset E).map f v = v ∘ f.unop.toOrderHom`, the range of a restricted
-- tuple is a subset of the range of the original, so closure under `.map` is
-- pure reindexing (`Set.range_comp_subset_range`). Fed to the generic
-- `supported_chain_complex` it yields, for free, the chain complex of affine
-- chains supported in `s` — the home of the subdivided fundamental chain.
def affine_subcomplex_of_set {E : Type u} (s : Set E) :
    (affine_sset E).Subcomplex where
  obj m := { v | Set.range v ⊆ s }
  map := by
    intro n m i x hx
    simp only [Set.mem_setOf_eq, Set.range_subset_iff] at hx ⊢
    intro z
    exact hx _

-- Forward rationale: Corestriction fact for the singular transport. The affine
-- realization of a simplex whose vertices lie in a convex set `s` stays in `s`.
-- Instantiated at `s = stdSimplex ℝ (Fin (n+1))` (convex), it lets each subdivided
-- fundamental-chain simplex be corestricted to a continuous map into Δⁿ, i.e. a
-- singular simplex of `TopCat.of (stdSimplex ℝ (Fin (n+1)))`. Route: the landed
-- `affine_simplex_map_range_convex_hull` places the point in `convexHull ℝ (range v)`,
-- then `convexHull_min hv hs` collapses that into `s`.
theorem affine_simplex_map_mem_of_convex {E : Type*} [NormedAddCommGroup E]
    [NormedSpace ℝ E] {s : Set E} (hs : Convex ℝ s) {n : ℕ} {v : Fin (n + 1) → E}
    (hv : Set.range v ⊆ s) (x : stdSimplex ℝ (Fin (n + 1))) :
    affine_simplex_map v x ∈ s :=
  convexHull_min hv hs (affine_simplex_map_range_subset_convexHull v (Set.mem_range_self x))

-- affine_centroid_mem: centroid of a family with range in a convex set stays in the set.
-- Rewrite centroid as affineCombination centroidWeights, use affineCombination_mem_convexHull
-- for membership in convexHull (range v), then convexHull_min hv hs shrinks it to s.
theorem affine_centroid_mem {E : Type u}
    [AddCommGroup E] [Module ℝ E] {s : Set E} (hs : Convex ℝ s) {n : ℕ}
    {v : Fin (n + 2) → E} (hv : Set.range v ⊆ s) :
    Finset.univ.centroid ℝ v ∈ s := by
  rw [Finset.centroid_def]
  refine convexHull_min hv hs ?_
  refine affineCombination_mem_convexHull ?_ ?_
  · intro i _
    rw [Finset.centroidWeights_apply]
    positivity
  · exact Finset.sum_centroidWeights_eq_one_of_nonempty ℝ Finset.univ (by simp)

-- Direct leaf-bypass: affine_cone b n = lmapDomain (Fin.cons b), so the cone of a
-- support-in-s chain is supported on (Fin.cons b) '' {range ⊆ s} ⊆ {range ⊆ s}
-- (range (cons b v) = insert b (range v) ⊆ s since b ∈ s and range v ⊆ s).
theorem affine_cone_supported {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] {s : Set E} {b : E} (hb : b ∈ s) (n : ℕ) :
    ∀ y ∈ Finsupp.supported R R {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ s},
      affine_cone (R := R) b n y ∈
        Finsupp.supported R R {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s} := by
  intro y hy
  rw [affine_cone]
  have hsub : (fun v => Fin.cons b v) '' {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ s}
      ⊆ {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s} := by
    rintro _ ⟨v, hv, rfl⟩
    change Set.range (Fin.cons b v) ⊆ s
    rw [Fin.range_cons]
    exact Set.insert_subset hb hv
  apply Finsupp.supported_mono hsub
  rw [← Finsupp.lmapDomain_supported]
  exact Submodule.mem_map_of_mem hy

-- Direct leaf-bypass: affine_cone b n = lmapDomain (Fin.cons b), so the cone of a
-- support-in-s chain is supported on (Fin.cons b) '' {range ⊆ s} ⊆ {range ⊆ s}
-- (range (cons b v) = insert b (range v) ⊆ s since b ∈ s and range v ⊆ s).
theorem affine_cone_supported' {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] {s : Set E} (b : E) (hb : b ∈ s) (n : ℕ) :
    ∀ x ∈ Finsupp.supported R R {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ s},
      affine_cone (R := R) b n x ∈ Finsupp.supported R R
        {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s} := affine_cone_supported hb n

-- centroid_mem_convex_of_range: centroid of a tuple with range in a convex set stays in the set.
-- Same recipe as `affine_centroid_mem`: rewrite centroid as affineCombination centroidWeights,
-- use affineCombination_mem_convexHull for membership in convexHull (range v), then
-- convexHull_min hv hs shrinks it to s.
theorem centroid_mem_convex_of_range {E : Type u}
    [AddCommGroup E] [Module ℝ E] {s : Set E} (hs : Convex ℝ s) (n : ℕ) :
    ∀ (v : (affine_sset E) _⦋n⦌), Set.range v ⊆ s →
      Finset.univ.centroid ℝ v ∈ s := by
  intro v hv
  rw [Finset.centroid_def]
  refine convexHull_min hv hs ?_
  refine affineCombination_mem_convexHull ?_ ?_
  · intro i _
    rw [Finset.centroidWeights_apply]
    positivity
  · exact Finset.sum_centroidWeights_eq_one_of_nonempty ℝ Finset.univ (by simp)

-- affine_face_supported: a single face map δ i preserves support-in-`s`
-- `δ i w = w ∘ i.succAbove` pointwise (defeq), so `range (δ i w) ⊆ range w ⊆ s`;
-- lift via `Finsupp.lmapDomain_supported` (image of `supported` is `supported` of
-- the image set) + `Finsupp.supported_mono`.
theorem affine_face_supported {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] {s : Set E} (n : ℕ) :
    ∀ (i : Fin (n + 2)) (z : ((affine_sset E) _⦋n + 1⦌ →₀ R)),
      z ∈ Finsupp.supported R R {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s} →
      Finsupp.lmapDomain R R ((affine_sset E).δ i) z ∈
      Finsupp.supported R R {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ s} := by
  intro i z hz
  have hmap : Finsupp.lmapDomain R R ((affine_sset E).δ i) z ∈
      Submodule.map (Finsupp.lmapDomain R R ((affine_sset E).δ i))
        (Finsupp.supported R R {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s}) :=
    Submodule.mem_map_of_mem hz
  rw [Finsupp.lmapDomain_supported] at hmap
  refine Finsupp.supported_mono ?_ hmap
  rintro w ⟨v, hv, rfl⟩
  refine Set.range_subset_iff.mpr fun j => ?_
  have hvj : Set.range v ⊆ s := hv
  exact hvj ⟨i.succAbove j, rfl⟩

-- ∂ preserves support-in-`s`: linearity (LinearMap.sum_apply) splits the boundary
-- into its face terms; Submodule.sum_mem + zsmul_mem reduce each to the single fact
-- that a face map keeps range ⊆ s (affine_face_supported).
theorem affine_boundary_supported {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] {s : Set E} (n : ℕ) :
    ∀ y ∈ Finsupp.supported R R {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s},
      (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
        • Finsupp.lmapDomain R R ((affine_sset E).δ i)) y ∈
        Finsupp.supported R R {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ s} := by
  intro y hy
  rw [LinearMap.sum_apply]
  refine Submodule.sum_mem _ fun i _ => ?_
  rw [LinearMap.smul_apply]
  exact zsmul_mem (affine_face_supported n i y hy) _

/-- Barycentric subdivision `affine_sd n` preserves the support-in-`s` condition, by
induction on `n`. Base `n = 0`: `affine_sd 0 = id` (`affine_sd_zero`), so support is
unchanged. Step `n+1`: rewrite `supported = span (single · 1 '' S)` and
`span_induction` reduces to a single generator `single v 1` with `range v ⊆ s`;
`affine_sd_succ_single` turns it into `affine_cone (centroid v) n (affine_sd n (∂ v))`,
then `affine_centroid_mem` (the centroid lies in `s`), `affine_boundary_supported`
(`∂` keeps support), the inductive hypothesis, and `affine_cone_supported` (coning on
an apex in `s` keeps support) compose; the add/smul/zero cases follow from linearity
of `affine_sd (n+1)`. -/
theorem affine_sd_supported {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] {s : Set E} (hs : Convex ℝ s) (n : ℕ) :
    ∀ x ∈ Finsupp.supported R R {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ s},
      affine_sd (R := R) n x ∈
        Finsupp.supported R R {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ s} := by
  induction n with
  | zero =>
      intro x hx
      rw [affine_sd_zero]
      simpa using hx
  | succ n ih =>
      intro x hx
      rw [Finsupp.supported_eq_span_single] at hx
      induction hx using Submodule.span_induction with
      | mem y hy =>
          obtain ⟨v, hv, rfl⟩ := hy
          rw [affine_sd_succ_single]
          apply affine_cone_supported (affine_centroid_mem hs hv) n
          apply ih
          exact affine_boundary_supported n _ (Finsupp.single_mem_supported R 1 hv)
      | zero => simp
      | add a b _ _ ha hb => rw [map_add]; exact Submodule.add_mem _ ha hb
      | smul r a _ ha => rw [map_smul]; exact Submodule.smul_mem _ _ ha

/-- Pointwise version of `affine_face_supported` (set images, not `Finsupp`):
`δ i w = w ∘ i.succAbove` pointwise (defeq), so `range (δ i w) ⊆ range w ⊆ s`. -/
theorem face_image_supported {E : Type u}
    [AddCommGroup E] [Module ℝ E] {s : Set E} (n : ℕ) (i : Fin (n + 2)) :
    (affine_sset E).δ i '' {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s} ⊆
      {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ s} := by
  rw [Set.image_subset_iff]
  rintro v hv
  simp only [Set.mem_preimage, Set.mem_setOf_eq]
  refine Set.range_subset_iff.mpr fun j => ?_
  have hvr : Set.range v ⊆ s := hv
  exact hvr ⟨i.succAbove j, rfl⟩

/-- The alternating boundary sum preserves support: expand the sum and zsmul
(`Submodule.sum_mem`, `zsmul_mem`), reducing each term to
`lmapDomain (δ i) x ∈ supported {w | range w ⊆ s}`. The one topological input is
`face_image_supported`: the `i`-th face carries the support set into itself;
`lmapDomain_supported` together with `supported_mono` then close each term. -/
theorem affine_boundary_supported' {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] {s : Set E} (n : ℕ) :
    ∀ x ∈ Finsupp.supported R R {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s},
      (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
        • Finsupp.lmapDomain R R ((affine_sset E).δ i)) x ∈ Finsupp.supported R R
        {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ s} := affine_boundary_supported n

/-- The cone homotopy `affine_ht n` preserves support in a convex set `s`: by
induction on `n`. Base case `n = 0`: `affine_ht 0 = 0` vanishes. Step: expand a
generator via `affine_ht_succ_single` to a cone on the centroid (in `s`, by
`affine_centroid_mem`) applied to `single v 1 − affine_ht n (∂ (single v 1))`, whose
boundary term stays supported by the inductive hypothesis together with
`affine_boundary_supported'`; `affine_cone_supported'` closes the coning step. -/
theorem affine_ht_supported {R : Type u} [Ring R] {E : Type u}
    [AddCommGroup E] [Module ℝ E] {s : Set E} (hs : Convex ℝ s) (n : ℕ) :
    ∀ x ∈ Finsupp.supported R R {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ s},
      affine_ht (R := R) n x ∈ Finsupp.supported R R
        {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s} := by
  induction n with
  | zero =>
      intro x hx
      have h0 : affine_ht (R := R) 0 x = 0 := by rw [affine_ht_zero]; rfl
      rw [h0]; exact Submodule.zero_mem _
  | succ n ih =>
      have hcone : ∀ (b : E), b ∈ s → ∀ y ∈ Finsupp.supported R R
            {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s},
          affine_cone (R := R) b (n + 1) y ∈ Finsupp.supported R R
            {w : (affine_sset E) _⦋n + 2⦌ | Set.range w ⊆ s} :=
        fun b hb => affine_cone_supported' b hb (n + 1)
      have hbdry : ∀ y ∈ Finsupp.supported R R
            {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s},
          (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
            • Finsupp.lmapDomain R R ((affine_sset E).δ i)) y ∈ Finsupp.supported R R
            {w : (affine_sset E) _⦋n⦌ | Set.range w ⊆ s} :=
        affine_boundary_supported' n
      have hcentroid : ∀ (v : (affine_sset E) _⦋n + 1⦌), Set.range v ⊆ s →
          Finset.univ.centroid ℝ v ∈ s :=
        centroid_mem_convex_of_range hs (n + 1)
      have key : Submodule.map (affine_ht (R := R) (n + 1))
            (Finsupp.supported R R {w : (affine_sset E) _⦋n + 1⦌ | Set.range w ⊆ s})
          ≤ Finsupp.supported R R {w : (affine_sset E) _⦋n + 2⦌ | Set.range w ⊆ s} := by
        rw [Finsupp.supported_eq_span_single, Submodule.map_span, Submodule.span_le]
        rintro _ ⟨_, ⟨v, hv, rfl⟩, rfl⟩
        simp only [SetLike.mem_coe]
        rw [affine_ht_succ_single]
        refine hcone (Finset.univ.centroid ℝ v) (hcentroid v hv) _ ?_
        refine Submodule.sub_mem _ (Finsupp.single_mem_supported R 1 hv) ?_
        exact ih _ (hbdry _ (Finsupp.single_mem_supported R 1 hv))
      intro x hx
      exact key (Submodule.mem_map_of_mem hx)

/-- Unfolds `affine_simplex_map` to the pointwise sum `∑ i, x i • Pi.single i 1`, then
`Finset.sum_ite_eq` collapses the Kronecker-delta sum to `x j` at each coordinate `j`.
This pins the base point of the singular transport: the affine realization of the
identity vertex tuple of `Δⁿ` is the subtype inclusion, so the fundamental affine
chain realizes to the IDENTITY singular simplex; this makes the `LinearMap.id` side
of the affine homotopy identity `∂T + T∂ = id − S` transport to the identity on
singular chains (Hatcher's `S σ = σ_# (sd Δⁿ)`). -/
theorem affine_simplex_map_single_tuple {n : ℕ}
    (x : stdSimplex ℝ (Fin (n + 1))) :
    affine_simplex_map (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) x
      = (x : Fin (n + 1) → ℝ) := by
  funext j
  simp only [affine_simplex_map, ContinuousMap.coe_mk, Finset.sum_apply, Pi.smul_apply,
    smul_eq_mul, Pi.single_apply, mul_ite, mul_one, mul_zero, Finset.sum_ite_eq, Finset.mem_univ,
    if_true]

/-- The corestricted realization morphism of simplicial sets: the analogue of the
affine realization restricted to `affine_subcomplex_of_set s` (vertex tuples valued in
a convex set `s`) and landing in the singular SSet of the subspace `s`. `app` sends
`⟨v, hv⟩` to the corestriction of `affine_simplex_map v` into `s` (membership by
`affine_simplex_map_mem_of_convex hs hv`); `naturality` peels the ULift/TopCat layers,
corestricts to the `E`-level equality, and closes by `std_simplex_map_weighted_sum`
(the barycentric weight pushforward identity). -/
noncomputable def affine_subcomplex_realization {E : Type u} [NormedAddCommGroup E]
    [NormedSpace ℝ E] {s : Set E} (hs : Convex ℝ s) :
    (affine_subcomplex_of_set s : SSet) ⟶ TopCat.toSSet.obj (TopCat.of s) where
  app n := TypeCat.ofHom (fun v => ULift.up (TopCat.ofHom
    (ContinuousMap.mk
      (fun x => (⟨affine_simplex_map v.1 (ULift.down x),
          affine_simplex_map_mem_of_convex hs v.2 (ULift.down x)⟩ : s))
      (((affine_simplex_map v.1).continuous.comp continuous_uliftDown).subtype_mk _))))
  naturality := by
    intro X Y f
    ext v
    simp only [Subfunctor.toFunctor_obj, Subfunctor.toFunctor_map, Functor.op_obj,
      SimplexCategory.toTop_obj, yoneda_obj_obj, SimplexCategory.toTop₀_obj,
      TypeCat.Fun.toFun_apply, comp_apply, TypeCat.hom_ofHom, TypeCat.Fun.coe_mk]
    simp only [TopCat.toSSet, CategoryTheory.uliftFunctor, CategoryTheory.uliftYoneda,
      CategoryTheory.Presheaf.restrictedULiftYoneda]
    simp only [Functor.comp_obj, Functor.whiskeringRight_obj_obj, Functor.whiskeringLeft_obj_obj,
      Functor.op_obj, SimplexCategory.toTop_obj, yoneda_obj_obj, Functor.comp_map, Functor.op_map,
      SimplexCategory.toTop_map, yoneda_obj_map, Quiver.Hom.unop_op, TypeCat.hom_ofHom,
      TypeCat.Fun.coe_mk]
    simp only [TopCat.uliftFunctor]
    congr 1
    ext x
    simp only [TopCat.hom_ofHom, ContinuousMap.coe_mk]
    change (affine_simplex_map ((affine_sset E).map f v.1)) (ULift.down x) =
        (affine_simplex_map v.1) (stdSimplex.map f.unop.toOrderHom (ULift.down x))
    exact (std_simplex_map_weighted_sum f.unop.toOrderHom (ULift.down x) v.1).symm

/-- The per-generator "transport" morphism for Hatcher's singular subdivision. For a
singular `n`-simplex `σ` of `X` it packages the corestricted affine realization
`affine_subcomplex_realization (convex_stdSimplex ℝ (Fin (n+1)))` (subdivided affine
chains on the standard simplex, valued in the simplex Set) postcomposed with
pushforward along the continuous map underlying `σ` (extracted via
`X.toSSetObjEquiv`). The result is a simplicial-set morphism
`affine_subcomplex_of_set (stdSimplex …) ⟶ TopCat.toSSet.obj X` whose `.app _⦋n⦌` on
the subdivided fundamental affine chain is the building block for `singular_sd` and
`singular_ht` (`Finsupp.linearCombination` over generators `σ` of
`Finsupp.lmapDomain` along this morphism), carrying the affine `∂T + T∂ = id − S`
identity to the singular level via naturality. -/
noncomputable def singular_transport {X : TopCat.{0}} {n : ℕ}
    (σ : (TopCat.toSSet.obj X) _⦋n⦌) :
    ((affine_subcomplex_of_set (stdSimplex ℝ (Fin (n + 1)) : Set (Fin (n + 1) → ℝ)) : SSet)
      ⟶ TopCat.toSSet.obj X) :=
  affine_subcomplex_realization (convex_stdSimplex ℝ (Fin (n + 1)))
    ≫ TopCat.toSSet.map (TopCat.ofHom (X.toSSetObjEquiv _ σ))

/-- Specialization of the general subdivision-support lemma `affine_sd_supported` to
`E = Fin (n+1) → ℝ`, `s = stdSimplex`, and the fundamental tuple `fun i => Pi.single i 1`.
The residual membership `single (fun i => Pi.single i 1) 1 ∈
supported {w | range w ⊆ stdSimplex}` closes via `Finsupp.single_mem_supported` and
`single_mem_stdSimplex` on each vertex. -/
theorem affine_sd_single_tuple_supported {R : Type} [Ring R] (n : ℕ) :
    affine_sd (R := R) (E := Fin (n + 1) → ℝ) n
        (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1) ∈
      Finsupp.supported R R
        {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ |
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))} := by
  apply affine_sd_supported (convex_stdSimplex ℝ (Fin (n + 1))) n
  apply Finsupp.single_mem_supported
  simp only [Set.mem_setOf_eq, Set.range_subset_iff]
  intro i
  exact single_mem_stdSimplex ℝ i

/-- Specialization of the general support-preservation lemma `affine_ht_supported`
(`affine_ht n` maps chains supported on tuples valued in a convex `s` to chains
supported on such tuples) to `s := stdSimplex ℝ (Fin (n+1))`, which is convex
(`convex_stdSimplex`), applied to the fundamental single chain. Its membership
witness reduces via `Finsupp.single_mem_supported` and `Set.range_subset_iff` to
`single_mem_stdSimplex` on each vertex `Pi.single i 1`. -/
theorem affine_ht_single_tuple_supported {R : Type} [Ring R] (n : ℕ) :
    affine_ht (R := R) n
        (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1) ∈
      Finsupp.supported R R
        {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n + 1⦌ |
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))} := by
  refine affine_ht_supported (convex_stdSimplex ℝ (Fin (n + 1))) n _ ?_
  exact Finsupp.single_mem_supported R 1
    (Set.range_subset_iff.2 (fun i => single_mem_stdSimplex ℝ i))

/-- Hatcher's barycentric subdivision operator `S` at the SINGULAR level — a
same-degree linear endomorphism of singular `n`-chains, transported from the affine
subdivision `affine_sd`. On a generator `σ` (a singular `n`-simplex of `X`), `S σ` is
the subdivided fundamental affine chain
`affine_sd n (single (fun i => Pi.single i 1) 1)` (supported in the standard simplex
by `affine_sd_single_tuple_supported`), corestricted to the level-`n` subtype
`{w | range w ⊆ stdSimplex}` via `Finsupp.subtypeDomain`, then pushed forward along
`(singular_transport σ).app` with `Finsupp.lmapDomain`. Built with
`Finsupp.linearCombination R` over generators (matching `affine_sd`), staying linear
over a noncommutative ring `R`. This is the singular-level engine on which the
generator equation, the chain-map identity `∂ ∘ S = S ∘ ∂` (via naturality of
`singular_transport` together with `affine_sd_boundary`/`affine_sd_map`), and
ultimately the small-simplices quasi-isomorphism for Mayer–Vietoris are built. `R` is
pinned to `Type` (universe 0) since `affine_sd` forces `R` and `E = Fin (n+1) → ℝ`
into one universe, and `singular_transport` is pinned to `TopCat.{0}`. -/
noncomputable def singular_sd {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ) :
    ((TopCat.toSSet.obj X) _⦋n⦌ →₀ R) →ₗ[R] ((TopCat.toSSet.obj X) _⦋n⦌ →₀ R) :=
  Finsupp.linearCombination R (fun σ =>
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
      (Finsupp.subtypeDomain
        (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
        (affine_sd (R := R) n
          (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))))

/-- The singular chain homotopy `T` (degree-raising companion of `singular_sd`): the
singular-level transport of the affine homotopy `affine_ht`. On a singular `n`-simplex
`σ`, apply `affine_ht n` to the fundamental affine `(n+1)`-tuple
`single (fun i => Pi.single i 1) 1`, corestrict (losslessly, by
`affine_ht_single_tuple_supported`) into the level-`(n+1)` standard-simplex subcomplex
via `Finsupp.subtypeDomain`, then push forward along `(singular_transport σ).app _⦋n+1⦌`
with `Finsupp.lmapDomain`. Same universe pin as `singular_sd` (`R : Type 0`,
`X : TopCat.{0}`). -/
noncomputable def singular_ht {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ) :
    ((TopCat.toSSet.obj X) _⦋n⦌ →₀ R) →ₗ[R] ((TopCat.toSSet.obj X) _⦋n + 1⦌ →₀ R) :=
  Finsupp.linearCombination R (fun σ =>
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n + 1⦌))
      (Finsupp.subtypeDomain
        (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n + 1⦌ =>
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
        (affine_ht (R := R) n
          (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))))

/-- Pure-geometric face compatibility for the singular transport, via
`TopCat.toSSetObjEquiv_δ_apply` and linearity of `FunOnFinite.linearMap` through
`affine_simplex_map`'s barycentric sum. The evaluation point
`⟨affine_simplex_map w.1 z, _⟩` is identified with `stdSimplex.map i.succAbove z'`
(via `stdSimplex.map_coe` together with `map_sum`/`map_smul` pushing the linear
pushforward through the barycentric combination), so the singular-adjunction
face-naturality lemma closes the goal directly. -/
theorem singular_transport_face_core
    {X : TopCat.{0}} {n : ℕ} (σ : (TopCat.toSSet.obj X) _⦋n + 1⦌)
    (i : Fin (n + 2)) {m : ℕ}
    (w : {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋m⦌ //
        Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))})
    (hw : Set.range (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘ w.1) ⊆
        stdSimplex ℝ (Fin (n + 2)))
    (z : stdSimplex ℝ (Fin (m + 1))) :
    (X.toSSetObjEquiv (Opposite.op ⦋n⦌)) ((TopCat.toSSet.obj X).δ i σ)
        ⟨affine_simplex_map w.1 z,
          affine_simplex_map_mem_of_convex (convex_stdSimplex ℝ (Fin (n + 1))) w.2 z⟩ =
      (X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌)) σ
        ⟨affine_simplex_map (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘ w.1) z,
          affine_simplex_map_mem_of_convex (convex_stdSimplex ℝ (Fin (n + 2))) hw z⟩ := by
  set z' : ↑(stdSimplex ℝ (Fin (n + 1))) :=
    (⟨affine_simplex_map w.1 z,
      affine_simplex_map_mem_of_convex (convex_stdSimplex ℝ (Fin (n + 1))) w.2 z⟩ :
      ↑(stdSimplex ℝ (Fin (n + 1)))) with hz'
  have hmap : stdSimplex.map i.succAbove z' =
      (⟨affine_simplex_map (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘ w.1) z,
        affine_simplex_map_mem_of_convex (convex_stdSimplex ℝ (Fin (n + 2))) hw z⟩ :
        ↑(stdSimplex ℝ (Fin (n + 2)))) := by
    apply stdSimplex.ext
    rw [stdSimplex.map_coe]
    change (FunOnFinite.linearMap ℝ ℝ i.succAbove) (affine_simplex_map w.1 z) =
      affine_simplex_map (⇑(FunOnFinite.linearMap ℝ ℝ i.succAbove) ∘ w.1) z
    simp only [affine_simplex_map, ContinuousMap.coe_mk, Function.comp_apply, map_sum, map_smul]
  rw [TopCat.toSSetObjEquiv_δ_apply, hmap]

/-- Evaluating `affine_subcomplex_realization`'s realization morphism on the fundamental
vertex tuple `(fun k => Pi.single k 1)` recovers the identity chart. The `toSSetObjEquiv`
layers over `TopCat.of (stdSimplex …)` peel off by defeq, reducing the goal to the affine
identity `∑ i, z i • Pi.single i 1 = z`, closed pointwise via `Pi.single_apply` and
`Finset.sum_ite_eq`. -/
theorem affine_subcomplex_realization_apply_eq_self {n : ℕ}
    (h : Set.range (fun k => (Pi.single k 1 : Fin (n + 1) → ℝ))
      ⊆ stdSimplex ℝ (Fin (n + 1)))
    (z : stdSimplex ℝ (Fin (n + 1))) :
    (TopCat.of (stdSimplex ℝ (Fin (n + 1)) : Set (Fin (n + 1) → ℝ))).toSSetObjEquiv
        (Opposite.op ⦋n⦌)
        ((affine_subcomplex_realization (convex_stdSimplex ℝ (Fin (n + 1)))).app (Opposite.op ⦋n⦌)
          ⟨fun k => (Pi.single k 1 : Fin (n + 1) → ℝ), h⟩) z = z := by
  apply Subtype.ext
  change (∑ i, (z : Fin (n+1) → ℝ) i • (Pi.single i 1 : Fin (n+1) → ℝ)) = (z : Fin (n+1) → ℝ)
  funext j
  simp [Pi.single_apply, Finset.sum_ite_eq]

/-- The space-direction naturality of `toSSetObjEquiv`: applying `toSSet.map (ofHom g)`
to a simplex `y` and then reading off its continuous map via the equiv is the same as
postcomposing `g` with `y`'s continuous map. Both `toSSet.map` and `toSSetObjEquiv`
unfold (through the restricted uLift-Yoneda embedding) to plain postcomposition, so
the identity holds definitionally. -/
theorem toSSetObjEquiv_map_naturality {X Y : TopCat.{0}} (g : C(Y, X)) (N : SimplexCategoryᵒᵖ)
    (y : (TopCat.toSSet.obj Y).obj N) (w : stdSimplex ℝ (Fin (N.unop.len + 1))) :
    X.toSSetObjEquiv N ((TopCat.toSSet.map (TopCat.ofHom g)).app N y) w
      = g (Y.toSSetObjEquiv N y w) := by rfl

end Library.AlgebraicTopology.MayerVietoris.AffineHomotopy
