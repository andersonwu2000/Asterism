import Library.AlgebraicTopology.MayerVietoris.AffineHomotopy
import Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
import Library.AlgebraicTopology.MayerVietoris.SingularSubdivisionHomotopy
import Library.AlgebraicTopology.MayerVietoris.SubdivisionMeshBound

/-!
# Small simplices for singular homology

This file proves the small-simplices (Lebesgue-number) theorem used in the proof of the
Mayer-Vietoris sequence for singular homology: given an open cover `X = A ∪ B`, every
singular chain is homologous to a chain subordinate to `{A, B}`, i.e. a sum of singular
simplices each landing wholly inside `A` or wholly inside `B`.

The argument iterates barycentric subdivision `singular_sd` on singular simplices. Since
subdivision commutes with the (affine) transport of the fundamental affine simplex along a
singular simplex `σ` (`singular_sd_pow_single`), and since the affine subdivision operator
shrinks simplices below any target diameter (fed into the Lebesgue number of the cover
`{σ⁻¹ A, σ⁻¹ B}` of the compact standard simplex), a sufficiently high subdivision power
`Sᵏ (single σ 1)` is already subordinate to `{A, B}` (`singular_sd_pow_small`). Linearity and
a finite-support uniformization argument extend this from a single generator to an arbitrary
chain (`singular_sd_pow_small_chain`). Finally, the iterated prism homotopy between `id` and
`Sᵏ` (`singular_sd_iter_homotopy`) shows that subdividing a chain, or the boundary of a
chain, changes nothing up to a boundary, giving the small-simplices theorem for both chains
(`singular_small_boundary_small`) and cycles (`singular_small_cycle_homologous`).

## Main statements

* `singular_sd_pow_small_chain`: some subdivision power of any singular chain is subordinate
  to an open cover `{A, B}`.
* `singular_small_boundary_small`: a chain subordinate to `{A, B}` that is a boundary is the
  boundary of a subordinate chain.
* `singular_small_cycle_homologous`: every cycle is homologous to a subordinate cycle.

## Implementation notes

Chains are represented as `Finsupp`s of singular simplices with coefficients in a ring `R`,
and "subordinate to `{A, B}`" is membership in the submodule
`Finsupp.supported R R {σ | Set.range σ ⊆ A} ⊔ Finsupp.supported R R {σ | Set.range σ ⊆ B}`.
-/

open Library.AlgebraicTopology.MayerVietoris.AffineHomotopy
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.MayerVietoris.SingularSubdivisionHomotopy
open Library.AlgebraicTopology.MayerVietoris.SubdivisionMeshBound
open Simplicial
open Simplicial CategoryTheory

namespace Library.AlgebraicTopology.MayerVietoris.SmallSimplicesTheorem

/-- Affine naturality of the `k`-th subdivision power on a generator: `Sᵏ (single v 1)` is
the pushforward of `Sᵏ (single fund 1)` along `Fintype.linearCombination ℝ v`
(`fund ↦ v`). Uses `sd_pow_map_naturality` (`Sᵏ` commutes with the pushforward
`lmapDomain (g ∘ ·)` for `g := linearCombination v`) together with
`linear_comb_pushforward_single_fund` (`g ∘ fund = v`, so the pushforward sends
`single fund 1 ↦ single v 1`). -/
theorem sd_pow_single_pushforward {R : Type} [Ring R] (n k : ℕ)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) :
    ((affine_sd (R := R) n) ^ k) (Finsupp.single v (1 : R))
      = Finsupp.lmapDomain R R
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            (⇑(Fintype.linearCombination ℝ v) ∘ w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌))
          (((affine_sd (R := R) n) ^ k)
            (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))  := by
  have hnat := sd_pow_map_naturality (R := R) (Fintype.linearCombination ℝ v) n k
  have hfund := linear_comb_pushforward_single_fund (R := R) n v
  rw [← hfund]
  exact LinearMap.congr_fun hnat _

/-- The LHS composite `transport σ ∘ subtypeDomain ∘ pushforward` is additive, so it
distributes over `c = ∑ u ∈ c.support, single u (c u)` (`Finsupp.sum_single`). Bundles
the three layers into one `AddMonoidHom` and applies `map_sum`. -/
theorem push_lhs_sum {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (c : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (Finsupp.lmapDomain R R
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              (⇑(Fintype.linearCombination ℝ v) ∘ w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌))
            c))
      = ∑ u ∈ c.support,
          Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (Finsupp.lmapDomain R R
                (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                  (⇑(Fintype.linearCombination ℝ v) ∘ w :
                    (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌))
                (Finsupp.single u (c u)))) := by
  set F : ((affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R) →+ (TopCat.toSSet.obj X _⦋n⦌ →₀ R) :=
    (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))).toAddMonoidHom.comp
      ((Finsupp.subtypeDomainAddMonoidHom
          (p := fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))).comp
        ((Finsupp.lmapDomain R R
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              (⇑(Fintype.linearCombination ℝ v) ∘ w :
                (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌))).toAddMonoidHom))
    with hF
  change F c = ∑ u ∈ c.support, F (Finsupp.single u (c u))
  conv_lhs => rw [show c = ∑ u ∈ c.support, Finsupp.single u (c u) from (Finsupp.sum_single c).symm]
  rw [map_sum]

/-- Bundles `lmapDomain ∘ subtypeDomain` (over the `σ`-transport of `⟨v, hv⟩`) as one
`AddMonoidHom`, then distributes it over the support decomposition
`c = ∑ u ∈ c.support, single u (c u)` (`Finsupp.sum_single`) via `map_sum`. -/
theorem push_rhs_sum {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)))
    (c : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R) :
    Finsupp.lmapDomain R R
        ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
          (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) c)
      = ∑ u ∈ c.support,
          Finsupp.lmapDomain R R
            ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
              (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single u (c u))) := by
  set F : ((affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R) →+ (TopCat.toSSet.obj X _⦋n⦌ →₀ R) :=
    (Finsupp.lmapDomain R R
        ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
          (Opposite.op ⦋n⦌))).toAddMonoidHom.comp
      (Finsupp.subtypeDomainAddMonoidHom
        (p := fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))) with hF
  change F c = ∑ u ∈ c.support, F (Finsupp.single u (c u))
  conv_lhs => rw [show c = ∑ u ∈ c.support, Finsupp.single u (c u) from (Finsupp.sum_single c).symm]
  rw [map_sum]

/-- The image of `lc v ∘ u` lies in the standard simplex whenever both `v` and `u` do:
pointwise via `Set.range_subset_iff`, `lc v (u j) = ∑ i, (u j) i • v i` is a convex
combination of the `v i ∈ stdSimplex` with weights `u j ∈ stdSimplex`, closed by
`Convex.sum_mem`. -/
theorem linear_comb_range_subset (n : ℕ)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (u : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)))
    (hu : Set.range u ⊆ stdSimplex ℝ (Fin (n + 1))) :
    Set.range (⇑(Fintype.linearCombination ℝ v) ∘ u :
      (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) ⊆ stdSimplex ℝ (Fin (n + 1))  := by
  intro x hx
  obtain ⟨j, rfl⟩ := hx
  rw [Function.comp_apply, Fintype.linearCombination_apply]
  exact Convex.sum_mem (convex_stdSimplex ℝ _)
    (fun i _ => (hu (Set.mem_range_self j)).1 i)
    (hu (Set.mem_range_self j)).2
    (fun i _ => hv (Set.mem_range_self i))

/-- Collapses the LHS generator via `Finsupp.mapDomain_single` twice (through the inner
linear-combination `lmapDomain`, then the `subtypeDomain` restriction) to
`single (transport ⟨lc v ∘ u, hmem⟩) r`, matching the RHS. -/
theorem push_gen_lhs {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (u : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (r : R)
    (hmem : Set.range (⇑(Fintype.linearCombination ℝ v) ∘ u :
      (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) ⊆ stdSimplex ℝ (Fin (n + 1))) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (Finsupp.lmapDomain R R
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              (⇑(Fintype.linearCombination ℝ v) ∘ w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌))
            (Finsupp.single u r)))
      = Finsupp.single ((singular_transport σ).app (Opposite.op ⦋n⦌)
          ⟨(⇑(Fintype.linearCombination ℝ v) ∘ u :
            (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌), hmem⟩) r := by
  classical
  have h1 : Finsupp.lmapDomain R R
      (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
        (⇑(Fintype.linearCombination ℝ v) ∘ w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌))
      (Finsupp.single u r)
      = Finsupp.single
          (⇑(Fintype.linearCombination ℝ v) ∘ u :
            (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) r := by
    rw [Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
  rw [h1]
  have h2 : Finsupp.subtypeDomain
      (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
        Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
      (Finsupp.single
        (⇑(Fintype.linearCombination ℝ v) ∘ u :
          (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) r)
      = Finsupp.single
          (⟨(⇑(Fintype.linearCombination ℝ v) ∘ u :
              (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌), hmem⟩ :
            {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ //
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))}) r := by
    apply Finsupp.ext
    intro a
    simp only [Finsupp.subtypeDomain_apply, Finsupp.single_apply, Subtype.ext_iff]
  erw [h2]
  erw [Finsupp.lmapDomain_apply, Finsupp.mapDomain_single]
  rfl

/-- Collapses `subtypeDomain (single u r)` to `single ⟨u, hu⟩ r` (via `Finsupp.ext` and
`Subtype.ext_iff`), then pushes the transport map through with `Finsupp.lmapDomain_apply`
and `Finsupp.mapDomain_single` to land on the transported single generator. -/
theorem push_gen_rhs {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)))
    (u : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (r : R)
    (hu : Set.range u ⊆ stdSimplex ℝ (Fin (n + 1))) :
    Finsupp.lmapDomain R R
        ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
          (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single u r))
      = Finsupp.single
          ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
            (Opposite.op ⦋n⦌) ⟨u, hu⟩) r := by
  have hsub :
      Finsupp.subtypeDomain
        (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
          Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single u r)
      = Finsupp.single
          (⟨u, hu⟩ :
            {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ //
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))}) r := by
    classical
    apply Finsupp.ext
    intro a
    simp only [Finsupp.subtypeDomain_apply, Finsupp.single_apply, Subtype.ext_iff]
  rw [hsub, Finsupp.lmapDomain_apply]
  exact Finsupp.mapDomain_single

/-- Barycentric associativity of singular transport on a single generator: the transport
of `⟨lc v ∘ u, hmem⟩` equals the double transport (first by `⟨v, hv⟩`, then by
`⟨u, hu⟩`). Follows from the proved composition law `singular_transport_comp`, whose
collapsed form is `transport σ` applied to a map that is defeq to `lc v ∘ u`. -/
theorem push_gen_transport_eq {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)))
    (u : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (hmem : Set.range (⇑(Fintype.linearCombination ℝ v) ∘ u :
      (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) ⊆ stdSimplex ℝ (Fin (n + 1)))
    (hu : Set.range u ⊆ stdSimplex ℝ (Fin (n + 1))) :
    (singular_transport σ).app (Opposite.op ⦋n⦌)
        ⟨(⇑(Fintype.linearCombination ℝ v) ∘ u :
          (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌), hmem⟩
      = (singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
          (Opposite.op ⦋n⦌) ⟨u, hu⟩  := by
  erw [singular_transport_comp σ ⟨v, hv⟩ ⟨u, hu⟩]
  congr 1

/-- Single-generator transport/pushforward composition law. Collapses each side of the
`single u r` generator to a `Finsupp.single` of one transported affine simplex via
`push_gen_lhs` and `push_gen_rhs`, and identifies the two transported vertices via
`push_gen_transport_eq` (barycentric associativity of the singular transport). -/
theorem push_gen {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)))
    (u : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (r : R)
    (hu : Set.range u ⊆ stdSimplex ℝ (Fin (n + 1))) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (Finsupp.lmapDomain R R
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              (⇑(Fintype.linearCombination ℝ v) ∘ w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌))
            (Finsupp.single u r)))
      = Finsupp.lmapDomain R R
          ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
            (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single u r))  := by
  classical
  have hmem : Set.range (⇑(Fintype.linearCombination ℝ v) ∘ u :
      (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) ⊆ stdSimplex ℝ (Fin (n + 1)) :=
    linear_comb_range_subset n v u hv hu
  have hlhs :
      Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (Finsupp.lmapDomain R R
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              (⇑(Fintype.linearCombination ℝ v) ∘ w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌))
            (Finsupp.single u r)))
        = Finsupp.single ((singular_transport σ).app (Opposite.op ⦋n⦌)
            ⟨(⇑(Fintype.linearCombination ℝ v) ∘ u :
              (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌), hmem⟩) r :=
    push_gen_lhs n σ v u r hmem
  have hrhs :
      Finsupp.lmapDomain R R
          ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
            (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single u r))
        = Finsupp.single
            ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
              (Opposite.op ⦋n⦌) ⟨u, hu⟩) r :=
    push_gen_rhs n σ v hv u r hu
  have htr :
      (singular_transport σ).app (Opposite.op ⦋n⦌)
          ⟨(⇑(Fintype.linearCombination ℝ v) ∘ u :
            (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌), hmem⟩
        = (singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
            (Opposite.op ⦋n⦌) ⟨u, hu⟩ :=
    push_gen_transport_eq n σ v hv u hmem hu
  rw [hlhs, hrhs]
  exact congrArg (fun t => Finsupp.single t r) htr

/-- Reduces the supported-chain transport/pushforward-collapse identity to one generator.
Both sides are additive in `c`, so distribute over `c = ∑ u ∈ c.support, single u (c u)`
(`push_lhs_sum`, `push_rhs_sum`); `Finset.sum_congr` then matches the summands
term-by-term, each closed by the per-generator identity `push_gen` using the range
membership supplied by `hc`. -/
theorem transport_subtype_pushforward_collapse {R : Type} [Ring R] {X : TopCat.{0}} (n : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)))
    (c : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R)
    (hc : c ∈ Finsupp.supported R R
      {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ | Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))}) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (Finsupp.lmapDomain R R
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              (⇑(Fintype.linearCombination ℝ v) ∘ w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌))
            c))
      = Finsupp.lmapDomain R R
          ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
            (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) c)  := by
  classical
  have hlhs := push_lhs_sum n σ v c
  have hrhs := push_rhs_sum n σ v hv c
  rw [hlhs, hrhs]
  refine Finset.sum_congr rfl (fun u hu => ?_)
  have hsub := (Finsupp.mem_supported (R := R) c).mp hc
  have hrange : Set.range u ⊆ stdSimplex ℝ (Fin (n + 1)) := hsub hu
  exact push_gen n σ v hv u (c u) hrange

/-- Geometric core (`r = 1`) of the Mayer-Vietoris subdivision-transport identity: the
`σ`-transport of the `v`-generator's `Sᵏ`-subdivision equals the `τ`-transport of the
fundamental generator's, where `τ := (singular_transport σ).app _ ⟨v, hv⟩`. Reduces
`Sᵏ (single v 1)` to a pushforward form via `sd_pow_single_pushforward` (affine
naturality), using that `Sᵏ (single fund 1)` is supported on `stdSimplex` tuples
(`sd_pow_fund_supported`), then collapses the transport of that pushforward via
`transport_subtype_pushforward_collapse`. -/
theorem transport_comp_fund {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌)
    (hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1))) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (((affine_sd (R := R) n) ^ k) (Finsupp.single v (1 : R))))
      = Finsupp.lmapDomain R R
          ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
            (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ k)
              (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)))  := by
  -- reduce `Sᵏ (single v 1)` to the pushforward form (h1), then collapse the transport (h2)
  have h1 := sd_pow_single_pushforward (R := R) n k v
  have hc := sd_pow_fund_supported (R := R) n k
  have h2 := transport_subtype_pushforward_collapse (R := R) n σ v hv _ hc
  rw [h1]
  exact h2

/-- Identifies the `σ`-transport of the `v`-generator's `Sᵏ`-subdivision with the
`r`-scaled `τ`-transport of the fundamental generator's, where
`τ := (singular_transport σ).app _ ⟨v, hv⟩`. Splits into `transport_scalar_factor`
(factoring `r` out through the three linear maps `Aᵏ`, `subtypeDomain P`,
`lmapDomain (transport σ)` via `single v r = r • single v 1`) and `transport_comp_fund`
(the geometric core at `r = 1`). -/
theorem transport_comp_smul_fund {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) (r : R)
    (hv : Set.range v ⊆ stdSimplex ℝ (Fin (n + 1))) :
    Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
        (Finsupp.subtypeDomain
          (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
            Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
          (((affine_sd (R := R) n) ^ k) (Finsupp.single v r)))
      = r • Finsupp.lmapDomain R R
          ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
            (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ k)
              (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)))  := by
  have h_scalar :
      Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ k) (Finsupp.single v r)))
        = r • Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k) (Finsupp.single v (1 : R)))) :=
    transport_scalar_factor n k σ v r
  have h_crux :
      Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ k) (Finsupp.single v (1 : R))))
        = Finsupp.lmapDomain R R
            ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
              (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))) :=
    transport_comp_fund n k σ v hv
  rw [h_scalar, h_crux]

/-- Single-generator transport naturality for `Sᵏ`, split into an LHS reduction and the
geometric transport-composition crux, joined through the common `r •`-scaled middle term
`r • lmapDomain (transport τ) (subtypeDomain P (Aᵏ (single fund 1)))`, where
`τ := (singular_transport σ).app _ ⟨v, hv⟩` is the transport of the affine generator `v`.
The LHS reduction pushes `lmapDomain (transport σ) ∘ subtypeDomain P` through `single v r`
to `single τ r`, factors `r`, then applies `ih` at `τ`; the RHS crux identifies the target
via `singular_transport_comp` (transport of `τ` is `σ` after `affine_simplex_map v`)
together with `affine_sd_map` naturality. -/
theorem singular_sd_pow_transport_comm_single {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (ih : ∀ (τ : (TopCat.toSSet.obj X) _⦋n⦌),
      ((singular_sd (R := R) (X := X) n) ^ k) (Finsupp.single τ 1)
        = Finsupp.lmapDomain R R ((singular_transport τ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)))) :
    ∀ (v : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌) (r : R),
      Set.range v ⊆ stdSimplex ℝ (Fin (n + 1)) →
      ((singular_sd (R := R) (X := X) n) ^ k)
          (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single v r)))
        = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k) (Finsupp.single v r)))  := by
  intro v r hv
  have h_lhs :
      ((singular_sd (R := R) (X := X) n) ^ k)
          (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) (Finsupp.single v r)))
        = r • Finsupp.lmapDomain R R
            ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
              (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))) := by
    exact singular_sd_pow_single_smul_transport_fund n k σ v r hv ih
  have h_rhs :
      Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ k) (Finsupp.single v r)))
        = r • Finsupp.lmapDomain R R
            ((singular_transport ((singular_transport σ).app (Opposite.op ⦋n⦌) ⟨v, hv⟩)).app
              (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))) := by
    exact transport_comp_smul_fund n k σ v r hv
  exact h_lhs.trans h_rhs.symm

/-- Reduces the generalized transport-naturality on an arbitrary std-supported affine
chain `c` to (1) the single-generator case `singular_sd_pow_transport_comm_single`
(threading `ih`, the hard crux via transport composition and affine-subdivision
naturality) and (2) a linear extension (`supported_linear_ext`) that lifts the generator
identity to all `c` supported in the standard simplex, using additivity of `Sᵏ`,
`lmapDomain`, `subtypeDomain` and `Aᵏ`. -/
theorem singular_sd_pow_transport_comm {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (ih : ∀ (τ : (TopCat.toSSet.obj X) _⦋n⦌),
      ((singular_sd (R := R) (X := X) n) ^ k) (Finsupp.single τ 1)
        = Finsupp.lmapDomain R R ((singular_transport τ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))))
    (c : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ →₀ R)
    (hc : c ∈ Finsupp.supported R R
      {w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ | Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))}) :
    ((singular_sd (R := R) (X := X) n) ^ k)
        (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1))) c))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ k) c))  := by
  have hg := singular_sd_pow_transport_comm_single n k σ ih
  exact supported_linear_ext n k σ hg c hc

/-- Reduces `Sᵏ (Ψ_σ (A e)) = Ψ_σ (A ^ (k + 1) e)` to the generalized transport-naturality
`singular_sd_pow_transport_comm` (`Sᵏ ∘ Ψ_σ = Ψ_σ ∘ Aᵏ` on any std-supported affine chain
`c`), instantiated at `c := A e` (support from `affine_sd_single_tuple_supported`);
`pow_succ` and `Module.End.mul_apply` rewrite `A ^ (k + 1) e = A ^ k (A e)` to close. -/
theorem singular_sd_pow_transport_succ {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (ih : ∀ (τ : (TopCat.toSSet.obj X) _⦋n⦌),
      ((singular_sd (R := R) (X := X) n) ^ k) (Finsupp.single τ 1)
        = Finsupp.lmapDomain R R ((singular_transport τ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)))) :
    ((singular_sd (R := R) (X := X) n) ^ k)
        (Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (affine_sd (R := R) n
              (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))))
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ (k + 1))
            (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)))  := by
  have hnat := singular_sd_pow_transport_comm (R := R) (X := X) n k σ ih
    (affine_sd (R := R) n (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1))
    (affine_sd_single_tuple_supported (R := R) n)
  rw [pow_succ, Module.End.mul_apply]
  exact hnat

/-- Inductive step of `singular_sd_pow_single`: peels one power via `pow_succ` and
`Module.End.mul_apply`, unfolds the innermost subdivision `S (single σ 1)` with
`singular_sd_single_gen`, leaving the transport-naturality crux
`singular_sd_pow_transport_succ`, which threads the `∀ τ` induction hypothesis through
`singular_transport_comp` and `affine_sd_map`. -/
theorem singular_sd_pow_single_succ {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌)
    (ih : ∀ (τ : (TopCat.toSSet.obj X) _⦋n⦌),
      ((singular_sd (R := R) (X := X) n) ^ k) (Finsupp.single τ 1)
        = Finsupp.lmapDomain R R ((singular_transport τ).app (Opposite.op ⦋n⦌))
            (Finsupp.subtypeDomain
              (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
                Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
              (((affine_sd (R := R) n) ^ k)
                (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)))) :
    ((singular_sd (R := R) (X := X) n) ^ (k + 1)) (Finsupp.single σ 1)
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ (k + 1))
              (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)))  := by
  rw [pow_succ, Module.End.mul_apply, singular_sd_single_gen]
  exact singular_sd_pow_transport_succ n k σ ih

/-- Computes `(singular_sd) ^ k` on a generator by induction on `k` (generalizing `σ` so
the induction hypothesis covers the transported simplices produced at each step). The
base case `k = 0` collapses both powers to the identity, leaving the fundamental
transport identity `single σ 1 = lmapDomain … (single fund 1)`
(`singular_transport_fund_single_gen`); the step folds the extra subdivision through
`singular_transport_comp` and `affine_sd_map`. -/
theorem singular_sd_pow_single {R : Type} [Ring R] {X : TopCat.{0}} (n k : ℕ)
    (σ : (TopCat.toSSet.obj X) _⦋n⦌) :
    ((singular_sd (R := R) (X := X) n) ^ k) (Finsupp.single σ 1)
      = Finsupp.lmapDomain R R ((singular_transport σ).app (Opposite.op ⦋n⦌))
          (Finsupp.subtypeDomain
            (fun w : (affine_sset (Fin (n + 1) → ℝ)) _⦋n⦌ =>
              Set.range w ⊆ stdSimplex ℝ (Fin (n + 1)))
            (((affine_sd (R := R) n) ^ k)
              (Finsupp.single (fun i => (Pi.single i 1 : Fin (n + 1) → ℝ)) 1)))  := by
  induction k generalizing σ with
  | zero =>
    simp only [pow_zero, Module.End.one_apply]
    exact (singular_transport_fund_single_gen n σ).symm
  | succ k ih =>
    exact singular_sd_pow_single_succ n k σ ih

/-- Small-simplices (Lebesgue-number) theorem for singular subdivision: every singular
generator `σ` has an iterate `(singular_sd ^ k) (single σ 1)` supported on generators
whose image lies wholly in `A` or wholly in `B`. Bridges `singular_sd_pow_single` (which
collapses `(singular_sd n) ^ k (single σ 1)` to `lmapDomain (transport σ)
(subtypeDomain _ ((affine_sd n) ^ k fund))`) with `singular_sd_lebesgue_cover`, which
produces the good iteration count `k` from the affine mesh decay `affine_sd_iter_diam`
and the Lebesgue number of the open cover `{σ⁻¹ A, σ⁻¹ B}` of the compact standard
simplex. -/
theorem singular_sd_pow_small
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ)
    (n : ℕ) (σ : (TopCat.toSSet.obj X) _⦋n⦌) :
    ∃ k : ℕ, ((singular_sd (R := R) (X := X) n) ^ k) (Finsupp.single σ 1) ∈
      Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ A} ⊔
        Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ B}  := by
  obtain ⟨k, hk⟩ := singular_sd_lebesgue_cover (R := R) hA hB hAB n σ
  refine ⟨k, ?_⟩
  rw [singular_sd_pow_single]
  refine lmap_mem_sup_supported _ _ _ _ (fun w hw => ?_)
  rcases hk w hw with h | h
  · exact Or.inl (singular_transport_range_hull σ w A h)
  · exact Or.inr (singular_transport_range_hull σ w B h)

/-- `singular_sd` preserves the `{A, B}`-supported sup submodule: it is `ℝ`-linear, so on
`x = y + z` with `y ∈ supported A` and `z ∈ supported B` (`Submodule.mem_sup`),
`singular_sd x = singular_sd y + singular_sd z` lands in the sup since each summand does,
via `singular_sd_supported` (per-set stability of subdivision). -/
theorem singular_sd_preserves_sup
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (_hA : IsOpen A) (_hB : IsOpen B) (_hAB : A ∪ B = Set.univ) (n : ℕ) :
    ∀ x ∈ (Finsupp.supported R R
              {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
                Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ A} ⊔
            Finsupp.supported R R
              {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
                Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ B}),
      (singular_sd (R := R) (X := X) n) x ∈
        (Finsupp.supported R R
              {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
                Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ A} ⊔
            Finsupp.supported R R
              {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
                Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ B}) := by
  intro x hx
  obtain ⟨y, hy, z, hz, hxeq⟩ := Submodule.mem_sup.mp hx
  rw [← hxeq, map_add]
  exact Submodule.add_mem_sup (singular_sd_supported A n y hy) (singular_sd_supported B n z hz)

/-- The chain `w' = Sᵏ w + Hₖ z` (with `Hₖ = ∑_{i<k} T ∘ Sⁱ`) is a boundary witness for
`z`, i.e. `z = ∂ w'`. Applies the iterated prism identity `∂ ∘ H + H ∘ ∂ = id - Sᵏ`
(`singular_sd_iter_homotopy`) at `w`, rewriting `∂ w = z` (`hzw`); pushing `∂` through the
resulting equation and using `∂ ∂ = 0` (`finsupp_boundary_sq_zero`) isolates
`∂ (Hₖ z) = z - ∂ (Sᵏ w)`, so `∂ (Sᵏ w + Hₖ z) = z`. -/
theorem small_boundary_witness_eq
    {R : Type} [Ring R] {X : TopCat.{0}}
    (n k : ℕ) (z : (TopCat.toSSet.obj X) _⦋n⦌ →₀ R)
    (w : (TopCat.toSSet.obj X) _⦋n + 1⦌ →₀ R)
    (hzw : z =
      (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
        • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) w) :
    z = (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
        • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
      (((singular_sd (R := R) (X := X) (n + 1)) ^ k) w
        + (∑ i ∈ Finset.range k, (@singular_ht R _ X n) ∘ₗ
            ((singular_sd (R := R) (X := X) n) ^ i)) z)  := by
  have hprism := LinearMap.congr_fun (singular_sd_iter_homotopy (R := R) (X := X) n k) w
  simp only [LinearMap.add_apply, LinearMap.comp_apply, LinearMap.sub_apply,
    LinearMap.id_apply] at hprism
  rw [← hzw] at hprism
  have hsq : ∀ y, (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
        • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i))
      ((∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ)
        • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) y) = 0 := by
    intro y
    have h := LinearMap.congr_fun (finsupp_boundary_sq_zero (R := R) (TopCat.toSSet.obj X) n) y
    simpa [LinearMap.comp_apply] using h
  have Q := congrArg (fun t => (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
        • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) t) hprism
  simp only [map_add, map_sub] at Q
  rw [hsq, ← hzw, zero_add] at Q
  rw [map_add, Q]
  abel

/-- If `(T ^ k)` sends every generator `single σ 1` of `c`'s support into `P`, then
`(T ^ k) c ∈ P`. Decomposes `c = ∑ σ ∈ c.support, c σ • single σ 1`, pushes `T ^ k` through
the finite sum by linearity (`map_sum`, `map_smul`), and closes each term with
`Submodule.smul_mem` and `Submodule.sum_mem`. -/
theorem pow_mem_of_forall_single_mem
    {R : Type} [Ring R] {ι : Type}
    (T : Module.End R (ι →₀ R)) (P : Submodule R (ι →₀ R))
    (c : ι →₀ R) (k : ℕ)
    (hk : ∀ σ ∈ c.support, (T ^ k) (Finsupp.single σ 1) ∈ P) :
    (T ^ k) c ∈ P  := by
  have hc : c = ∑ σ ∈ c.support, c σ • Finsupp.single σ 1 := by
    conv_lhs => rw [← Finsupp.sum_single c]
    rw [Finsupp.sum]
    refine Finset.sum_congr rfl ?_
    intro σ _
    rw [Finsupp.smul_single, smul_eq_mul, mul_one]
  rw [hc, map_sum]
  apply Submodule.sum_mem
  intro σ hσ
  rw [map_smul]
  exact Submodule.smul_mem P _ (hk σ hσ)

/-- The prism operator `singular_ht` preserves the `{A, B}`-supported sup submodule.
Splits `y = a + b` via `Submodule.mem_sup`, pushes each summand through
`singular_ht_supported` (with `U := A` / `U := B`), then recombines with `map_add`. -/
theorem singular_ht_sup
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (n : ℕ) (y : (TopCat.toSSet.obj X) _⦋n⦌ →₀ R)
    (hy : y ∈
      Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ A} ⊔
        Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ B}) :
    (@singular_ht R _ X n) y ∈
      Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ A} ⊔
        Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ B} := by
  rw [Submodule.mem_sup] at hy
  obtain ⟨a, ha, b, hb, hab⟩ := hy
  rw [← hab, map_add]
  exact Submodule.add_mem_sup (singular_ht_supported A n a ha) (singular_ht_supported B n b hb)

/-- `singular_sd` iterated `i` times preserves membership in the `{A, B}`-supported sup
submodule. Induction on `i`: the base case `i = 0` is `singular_sd ^ 0 = id`, and the step
uses `singular_sd_supported` (per-set stability of subdivision) applied to the
`Submodule.mem_sup` decomposition, recombined via `Submodule.add_mem_sup`. -/
theorem singular_sd_pow_supported
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (n : ℕ) (z : (TopCat.toSSet.obj X) _⦋n⦌ →₀ R)
    (hz : z ∈
      Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ A} ⊔
        Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ B})
    (i : ℕ) :
    ((singular_sd (R := R) (X := X) n) ^ i) z ∈
      Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ A} ⊔
        Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ B}  := by
  induction i with
  | zero => simpa using hz
  | succ k ih =>
    rw [pow_succ', Module.End.mul_apply]
    obtain ⟨y, hy, w, hw, hxeq⟩ := Submodule.mem_sup.mp ih
    rw [← hxeq, map_add]
    exact Submodule.add_mem_sup (singular_sd_supported A n y hy) (singular_sd_supported B n w hw)

/-- The iterated prism chain `Hₖ z = ∑_{i<k} (T ∘ Sⁱ) z` stays subordinate to `{A, B}`.
Distributes the sum (`LinearMap.sum_apply` and `Submodule.sum_mem`); each term is
`T (Sⁱ z)`, where `Sⁱ z` stays in the sup (`singular_sd_pow_supported`) and `T` preserves
the sup (`singular_ht_sup`). -/
theorem singular_ht_sum_supported
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (n k : ℕ) (z : (TopCat.toSSet.obj X) _⦋n⦌ →₀ R)
    (hz : z ∈
      Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ A} ⊔
        Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ B}) :
    (∑ i ∈ Finset.range k, (@singular_ht R _ X n) ∘ₗ
        ((singular_sd (R := R) (X := X) n) ^ i)) z ∈
      Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ A} ⊔
        Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ B}  := by
  rw [LinearMap.sum_apply]
  apply Submodule.sum_mem
  intro i _
  rw [LinearMap.comp_apply]
  exact singular_ht_sup n _ (singular_sd_pow_supported n z hz i)

/-- If `T` stabilizes `P` and `(T ^ m) x ∈ P`, then `(T ^ n) x ∈ P` for every `n ≥ m`.
Proved by `Nat.le_induction` from the base `m`, using `T`-invariance of `P` (`hstab`) and
`pow_succ' : T ^ (n + 1) = T * T ^ n` to push the extra `T` onto the already-in-`P` term
`(T ^ n) x`. -/
theorem pow_mem_of_ge
    {R : Type} [Ring R] {ι : Type}
    (T : Module.End R (ι →₀ R)) (P : Submodule R (ι →₀ R))
    (hstab : ∀ x ∈ P, T x ∈ P)
    (x : ι →₀ R) (m n : ℕ) (hmn : m ≤ n) (hx : (T ^ m) x ∈ P) :
    (T ^ n) x ∈ P := by
  induction n, hmn using Nat.le_induction with
  | base => exact hx
  | succ n hmn ih =>
    rw [pow_succ', Module.End.mul_apply]
    exact hstab _ ih

/-- Finite-support uniformization of per-generator powers: reduce to `pow_mem_of_ge`
(`P` absorbs higher powers of `T` once a lower power lands in `P`), then take the common
exponent as the supremum of the per-generator choices over the finite support `c.support`
(each choice is `≤` the supremum via `Finset.le_sup`). -/
theorem uniform_k_of_gen
    {R : Type} [Ring R] {ι : Type}
    (T : Module.End R (ι →₀ R)) (P : Submodule R (ι →₀ R))
    (hstab : ∀ x ∈ P, T x ∈ P)
    (c : ι →₀ R)
    (hgen : ∀ σ : ι, ∃ k : ℕ, (T ^ k) (Finsupp.single σ 1) ∈ P) :
    ∃ k : ℕ, ∀ σ ∈ c.support, (T ^ k) (Finsupp.single σ 1) ∈ P  := by
  classical
  refine ⟨c.support.sup (fun σ => (hgen σ).choose), ?_⟩
  intro σ hσ
  exact pow_mem_of_ge T P hstab (Finsupp.single σ 1) (hgen σ).choose _
    (Finset.le_sup (f := fun σ => (hgen σ).choose) hσ) (hgen σ).choose_spec

/-- Finite-support uniformization: if every generator eventually lands in the invariant
submodule `P`, a common power `k` works for the whole chain `c`. Combines
`uniform_k_of_gen` (a single `k` discharging every generator in `c.support`) with linearity
of `T ^ k` (`pow_mem_of_forall_single_mem`). -/
theorem uniform_pow_of_gen_mem
    {R : Type} [Ring R] {ι : Type}
    (T : Module.End R (ι →₀ R)) (P : Submodule R (ι →₀ R))
    (hstab : ∀ x ∈ P, T x ∈ P)
    (c : ι →₀ R)
    (hgen : ∀ σ : ι, ∃ k : ℕ, (T ^ k) (Finsupp.single σ 1) ∈ P) :
    ∃ k : ℕ, (T ^ k) c ∈ P  := by
  obtain ⟨k, hk⟩ := uniform_k_of_gen T P hstab c hgen
  exact ⟨k, pow_mem_of_forall_single_mem T P c k hk⟩

/-- Chain-level small-simplices theorem: lift the single-generator keystone
`singular_sd_pow_small` to an arbitrary chain `c`. The abstract finite-support
uniformization `uniform_pow_of_gen_mem` gives a common power `k` working for the whole
chain, fed by the per-generator existence (`singular_sd_pow_small`) and the single-step
invariance of `C(A) ⊔ C(B)` under `singular_sd` (`singular_sd_preserves_sup`). -/
theorem singular_sd_pow_small_chain
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ)
    (n : ℕ) (c : (TopCat.toSSet.obj X) _⦋n⦌ →₀ R) :
    ∃ k : ℕ, ((singular_sd (R := R) (X := X) n) ^ k) c ∈
      Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ A} ⊔
        Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ B}  := by
  refine uniform_pow_of_gen_mem (singular_sd (R := R) (X := X) n) _ ?_ c ?_
  · exact singular_sd_preserves_sup hA hB hAB n
  · intro σ; exact singular_sd_pow_small hA hB hAB n σ

/-- If a chain `z = ∂ w` is subordinate to `{A, B}`, it is the boundary of a subordinate
`(n + 1)`-chain: choose `k` with `Sᵏ w` small (`singular_sd_pow_small_chain`), and take the
witness `w' = Sᵏ w + Hₖ z`, where `Hₖ = ∑_{i<k} T ∘ Sⁱ` is the iterated prism operator.
`Hₖ z` stays subordinate to `{A, B}` since `T` and `S` both preserve support
(`singular_ht_sum_supported`), and `z = ∂ w'` follows from the Hatcher prism identity
`∂ ∘ H + H ∘ ∂ = id - Sᵏ` (`singular_sd_iter_homotopy`) together with `∂ ∂ = 0`
(`finsupp_boundary_sq_zero`) and `∂ w = z` (`small_boundary_witness_eq`). -/
theorem singular_small_boundary_small
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ)
    (n : ℕ) (z : (TopCat.toSSet.obj X) _⦋n⦌ →₀ R)
    (w : (TopCat.toSSet.obj X) _⦋n + 1⦌ →₀ R)
    (hzsmall : z ∈
      Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ A} ⊔
        Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n⦌) τ) ⊆ B})
    (hzw : z =
      (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
        • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) w) :
    ∃ w' : (TopCat.toSSet.obj X) _⦋n + 1⦌ →₀ R,
      w' ∈
        Finsupp.supported R R
            {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
              Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ A} ⊔
          Finsupp.supported R R
            {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
              Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ B} ∧
        z = (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ)
          • Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) w'  := by
  obtain ⟨k, hk⟩ := singular_sd_pow_small_chain hA hB hAB (n + 1) w
  have h_small := singular_ht_sum_supported n k z hzsmall
  have h_bd := small_boundary_witness_eq n k z w hzw
  exact ⟨((singular_sd (R := R) (X := X) (n + 1)) ^ k) w
      + (∑ i ∈ Finset.range k, (@singular_ht R _ X n) ∘ₗ
          ((singular_sd (R := R) (X := X) n) ^ i)) z,
    Submodule.add_mem _ hk h_small, h_bd⟩

/-- Every `(n + 1)`-cycle `z` is homologous to an `{A, B}`-small cycle `z'`: pick the
subdivision power `k` making `z' := Sᵏ z` small via the chain-level Lebesgue theorem
`singular_sd_pow_small_chain`; `z'` is again a cycle since `Sᵏ` commutes with `∂`
(`singular_sd_pow_boundary`); and `z - z' = ∂ w` for `w := Hₖ z`, the iterated prism
operator, via the Hatcher homotopy `∂ ∘ H + H ∘ ∂ = id - Sᵏ`
(`singular_sd_iter_homotopy`). -/
theorem singular_small_cycle_homologous
    {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (n : ℕ)
    (z : (TopCat.toSSet.obj X) _⦋n + 1⦌ →₀ R)
    (hz : (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) •
        Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) z = 0) :
    ∃ (z' : (TopCat.toSSet.obj X) _⦋n + 1⦌ →₀ R)
      (w : (TopCat.toSSet.obj X) _⦋n + 2⦌ →₀ R),
      z' ∈ Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ A} ⊔
        Finsupp.supported R R
          {τ : (TopCat.toSSet.obj X) _⦋n + 1⦌ |
            Set.range ⇑(X.toSSetObjEquiv (Opposite.op ⦋n + 1⦌) τ) ⊆ B} ∧
      (∑ i : Fin (n + 2), (-1 : ℤ) ^ (i : ℕ) •
          Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) z' = 0 ∧
      z - z' = (∑ i : Fin (n + 3), (-1 : ℤ) ^ (i : ℕ) •
          Finsupp.lmapDomain R R ((TopCat.toSSet.obj X).δ i)) w  := by
  obtain ⟨k, hk⟩ := singular_sd_pow_small_chain hA hB hAB (n + 1) z
  refine ⟨((singular_sd (R := R) (X := X) (n + 1)) ^ k) z,
      (∑ i ∈ Finset.range k,
        (@singular_ht R _ X (n + 1)) ∘ₗ (singular_sd (R := R) (X := X) (n + 1)) ^ i) z,
      hk, ?_, ?_⟩
  · have hcomm := LinearMap.congr_fun (singular_sd_pow_boundary (R := R) (X := X) n k) z
    simp only [LinearMap.comp_apply] at hcomm
    rw [hz, map_zero] at hcomm
    exact hcomm.symm
  · have hhom := LinearMap.congr_fun (singular_sd_iter_homotopy (R := R) (X := X) n k) z
    simp only [LinearMap.add_apply, LinearMap.comp_apply, LinearMap.sub_apply,
      LinearMap.id_apply] at hhom
    rw [hz, map_zero, add_zero] at hhom
    exact hhom.symm

end Library.AlgebraicTopology.MayerVietoris.SmallSimplicesTheorem
