import Library.AlgebraicTopology.MayerVietoris.LongExactSequence
import Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
import Library.AlgebraicTopology.SphereHomology.SphereMVPairAndDeltaIso
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

/-!
# The Mayer–Vietoris connecting map for spheres

This file specializes the Mayer–Vietoris long exact sequence for singular homology
(`Library.AlgebraicTopology.MayerVietoris.LongExactSequence`) to the cover of a sphere
`S^{n+2}` by the two open sets obtained by removing a single antipodal point from each
of the north and south poles. The two pieces of this cover, and their intersection, are
each contractible or homotopy equivalent to a lower sphere, which lets us identify the
connecting map `δ : H_1(S^{n+2}) → H_0(A ∩ B)` of the sequence as a monomorphism, and
express `H_{n+1}(X)` as a kernel of the Mayer–Vietoris boundary map.

## Main definitions

* `mv_connecting_kernel_iso`: when the pair-complex homology `H_{n+1}(C(A) ⊕ C(B))`
  vanishes, `H_{n+1}(X; R)` is isomorphic to the kernel of the Mayer–Vietoris
  boundary map at level `n`.

## Main statements

* `sphere_h1_delta_mono`: the Mayer–Vietoris connecting map
  `δ : H_1(S^{n+2}) → H_0(A ∩ B)` is a monomorphism.
-/

open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.LongExactSequence
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
open Library.AlgebraicTopology.SphereHomology.SphereMVPairAndDeltaIso
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.SphereMVConnectingMap

variable {R : Type} [Ring R]

/-- If the pair-complex homology `H_{n+1}(C(A) ⊕ C(B))` vanishes for a Mayer–Vietoris
cover `A ∪ B = X`, then the singular homology `H_{n+1}(X; R)` is isomorphic to the
kernel of the Mayer–Vietoris boundary map
`H_n(C(A) ∩ C(B)) → H_n(C(A) ⊕ C(B))`. -/
noncomputable def mv_connecting_kernel_iso {X : TopCat.{0}}
    {A B : Set X} (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (n : ℕ)
    (hpair : IsZero
      (((mv_short_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A)
          (singular_subcomplex_of_set X B)).X₂).homology (n + 1))) :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) (n + 1)).obj
        (ModuleCat.of R R)).obj X ≅
      kernel (HomologicalComplex.homologyMap
        (mv_short_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A) (singular_subcomplex_of_set X B)).f n) := by
  haveI hqi : QuasiIso (supported_chain_complex_incl
      (R := R) (TopCat.toSSet.obj X)
      (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) :=
    Library.AlgebraicTopology.MayerVietoris.LongExactSequence.mv_incl_quasi_iso hA hB hAB
  have hexact := Library.AlgebraicTopology.MayerVietoris.LongExactSequence.mv_les_exact_inter
    (R := R) hA hB hAB n
  haveI hmono : Mono (Library.AlgebraicTopology.MayerVietoris.LongExactSequence.mv_delta
    hA hB hAB n) := mv_delta_mono hA hB hAB n hpair
  exact (supported_top_homology_iso X (n + 1)).symm ≪≫
    IsLimit.conePointUniqueUpToIso
      (@CategoryTheory.ShortComplex.Exact.fIsKernel _ _ _ _ _ hexact hmono)
      (limit.isLimit _)

/-- The Mayer–Vietoris connecting map `mv_delta` composed with the induced map on
`H₀` of the inclusion of the intersection into the pair complex vanishes: this is the
`δ_comp` composition-zero fact baked into `mv_les_exact_inter`'s short complex, unfolded
here directly for `n = 0`. Unfolding `mv_delta` to `inv (homologyMap incl 1) ≫ δ 1 0 rfl`
and reassociating, `mv_short_complex_short_exact.δ_comp` gives
`δ 1 0 rfl ≫ f = homologyMap incl 1`, closed by `IsIso.eq_inv_comp`. -/
theorem delta_comp_inter_incl_zero (n : ℕ)
    (hA : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ -1})
    (hB : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ 1})
    (hAB : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ -1} ∪
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ 1} = Set.univ) :
    mv_delta (R := R)
        (X := TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
        hA hB hAB 0
      ≫ HomologicalComplex.homologyMap
          (mv_short_complex (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1)))
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                x.1 (Fin.last (n+2)) ≠ -1})
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                x.1 (Fin.last (n+2)) ≠ 1})).f 0 = 0 := by
  simp only [mv_delta, Category.assoc]
  exact IsIso.eq_inv_comp _ |>.mp
    ((mv_short_complex_short_exact (R := R)
        (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1)))
        (singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
            x.1 (Fin.last (n+2)) ≠ -1})
        (singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
            x.1 (Fin.last (n+2)) ≠ 1})).δ_comp (0 + 1) 0 rfl)

/-- For `j ≥ 1`, the singular homology `H_j` of the pair complex `C(A) ⊕ C(B)` vanishes
for the polar-complement cover of `S^{n+2}` by the two open sets missing the north,
respectively south, pole: both pieces are contractible, so their reduced homology
vanishes in every positive degree. -/
theorem pair_term_homology_vanishes (n j : ℕ) (hj : 1 ≤ j) :
    IsZero
      ((mv_short_complex (R := R)
        (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1)))
        (singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1 | x.1 (Fin.last (n+1)) ≠ -1})
        (singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1 |
            x.1 (Fin.last (n+1)) ≠ 1})).X₂.homology j) :=
  mv_pair_homology_zero (R := R) n j hj

/-- The degree-`1` homology of the pair complex `C(A) ⊕ C(B)` for the polar-complement
cover of `S^{n+2}` vanishes: an instance of `pair_term_homology_vanishes` at `j = 1`. -/
theorem sphere_h1_pair_is_zero (n : ℕ) :
    IsZero (HomologicalComplex.homology
      (mv_short_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1)))
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
            {x | x.1 (Fin.last (n+2)) ≠ -1})
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
            {x | x.1 (Fin.last (n+2)) ≠ 1})).X₂ (0 + 1)) := by
  exact pair_term_homology_vanishes (R := R) (n+1) (0+1) (by norm_num)

/-- The Mayer–Vietoris connecting map `δ = mv_delta … 0 : H_1(C(S^{n+2})) → H_0(C(A ∩ B))`
is a monomorphism. This follows from total-spot exactness of the Mayer–Vietoris long
exact sequence (`mv_les_exact_total`): the incoming map's source is `H_1` of the pair
complex `C(A) ⊕ C(B)`, which vanishes by `sphere_h1_pair_is_zero` since both polar caps
are contractible. So the incoming map is `0`, and `ShortComplex.Exact.mono_g` forces
`δ` to be mono. -/
theorem sphere_h1_delta_mono (n : ℕ)
    (hA : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ -1})
    (hB : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ 1})
    (hAB : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ -1} ∪
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ 1} = Set.univ) :
    CategoryTheory.Mono
      (mv_delta (R := R) (X := TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
        hA hB hAB 0) := by
  have hexact := mv_les_exact_total (R := R)
      (X := TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1)) hA hB hAB 0
  have hzero : IsZero (HomologicalComplex.homology
      (mv_short_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1)))
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
            {x | x.1 (Fin.last (n+2)) ≠ -1})
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
            {x | x.1 (Fin.last (n+2)) ≠ 1})).X₂ (0 + 1)) :=
    sphere_h1_pair_is_zero (R := R) n
  exact hexact.mono_g (hzero.eq_zero_of_src _)

end Library.AlgebraicTopology.SphereHomology.SphereMVConnectingMap
