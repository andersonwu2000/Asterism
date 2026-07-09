import Mathlib.Algebra.Category.ModuleCat.Abelian
import Mathlib.Algebra.Category.ModuleCat.Colimits
import Mathlib.Algebra.Lie.OfAssociative
import Mathlib.Algebra.Ring.IsFormallyReal
import Mathlib.AlgebraicTopology.SingularHomology.HomologyZero
import Mathlib.Analysis.Normed.Module.Connected
import Mathlib.Data.Real.StarOrdered
import Mathlib.Geometry.Manifold.Instances.Sphere
import Mathlib.Topology.Category.TopCat.Sphere
import Library.AlgebraicTopology.SphereHomology.HomotopyInvariance

namespace Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps

/-!
# Connectivity and polar caps of spheres

This file establishes point-set topology facts about the topological spheres `TopCat.sphere n`
that feed into the computation of their singular homology: spheres are path-connected, the
complement of a point in a sphere is contractible (via stereographic projection onto an
orthogonal complement), and consequently the two polar "caps" obtained by removing a coordinate
pole `x.1 (Fin.last (n + 1)) = ±1` from the sphere are contractible.

## Main statements

* `sphere_path_connected_space`: `TopCat.sphere n` is path-connected for `n ≥ 1`.
* `sphere_compl_point_contractible`: a sphere with one point removed is contractible.
* `sphere_cap_contractible`: both polar caps of a sphere are contractible.
* `sphere_homology_zero`: the zeroth singular homology of `TopCat.sphere n` (`n ≥ 1`) is `R`.

## Implementation notes

A polar cap is described as the complement of a single "pole" point
`EuclideanSpace.single (Fin.last _) c` with `c = ±1`; `sphere_pole_coord_eq` identifies this pole
with the set where the last coordinate equals `c`.
-/

/-- The topological sphere `TopCat.sphere n` is path-connected for `n ≥ 1`. This is obtained by
transporting path-connectedness of the Euclidean metric sphere `Metric.sphere 0 1` in
`EuclideanSpace ℝ (Fin (n + 1))` (whose rank $n + 1$ exceeds `1`) across `Homeomorph.ulift`. -/
theorem sphere_path_connected_space (n : ℕ) (hn : 1 ≤ n) :
    PathConnectedSpace (TopCat.sphere n) := by
  have hrank : 1 < Module.rank ℝ (EuclideanSpace ℝ (Fin (n + 1))) := by
    rw [← Module.finrank_eq_rank, finrank_euclideanSpace_fin]
    exact_mod_cast Nat.lt_add_of_pos_left (by omega)
  have hpc : IsPathConnected (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 1))) 1) :=
    isPathConnected_sphere hrank 0 zero_le_one
  have hspace : PathConnectedSpace ↥(Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 1))) 1) :=
    isPathConnected_iff_pathConnectedSpace.mp hpc
  exact Homeomorph.ulift.symm.surjective.pathConnectedSpace Homeomorph.ulift.symm.continuous

section OrthogonalComplement

variable {E : Type} [NormedAddCommGroup E] [InnerProductSpace ℝ E] {v : E}

/-- The orthogonal complement `(ℝ ∙ v)ᗮ` of a line in a real inner product space is contractible,
since every real topological vector space is contractible. -/
theorem orthogonal_complement_contractible : ContractibleSpace ↥((ℝ ∙ v)ᗮ) :=
  RealTopologicalVectorSpace.contractibleSpace

/-- The complement of a point `v` on the unit sphere in `E` is homeomorphic, via stereographic
projection `stereographic hv`, to the orthogonal complement `(ℝ ∙ v)ᗮ` of the line through `v`. -/
noncomputable def sphere_compl_point_homeo_orthogonal (hv : ‖v‖ = 1)
    (hv' : v ∈ Metric.sphere (0 : E) 1) :
    ↥({(⟨v, hv'⟩ : Metric.sphere (0 : E) 1)}ᶜ : Set (Metric.sphere (0 : E) 1)) ≃ₜ
      ↥((ℝ ∙ v)ᗮ) :=
  (stereographic hv).toHomeomorphSourceTarget.trans (Homeomorph.Set.univ _)

/-- The unit sphere in a real inner product space with one point removed is contractible: it is
homeomorphic, via stereographic projection, to the (contractible) orthogonal complement of that
point. -/
theorem sphere_compl_point_contractible (hv : ‖v‖ = 1) (hv' : v ∈ Metric.sphere (0 : E) 1) :
    ContractibleSpace
      ↥({(⟨v, hv'⟩ : Metric.sphere (0 : E) 1)}ᶜ : Set (Metric.sphere (0 : E) 1)) := by
  have h1 := sphere_compl_point_homeo_orthogonal hv hv'
  have h2 : ContractibleSpace ↥((ℝ ∙ v)ᗮ) := orthogonal_complement_contractible
  exact @Homeomorph.contractibleSpace _ _ _ _ h2 h1

end OrthogonalComplement

section PolarCaps

variable (n : ℕ) (c : ℝ)

/-- If a unit-sphere point `x` has last coordinate `x.1 (Fin.last (n + 1)) = c` with `c = ±1`,
then every other coordinate of `x` vanishes. -/
theorem sphere_off_pole_coord_zero (hc : c = 1 ∨ c = -1)
    (x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1)
    (hx : x.1 (Fin.last (n + 1)) = c) :
    ∀ i : Fin (n + 2), i ≠ Fin.last (n + 1) → x.1 i = 0 := by
  intro i hi
  have hnorm : ‖x.1‖ = 1 := mem_sphere_zero_iff_norm.mp x.2
  have hsq : ∑ j : Fin (n + 2), (x.1 j) ^ 2 = 1 := by
    rw [← EuclideanSpace.real_norm_sq_eq, hnorm]; norm_num
  have hlast : (x.1 (Fin.last (n + 1))) ^ 2 = 1 := by
    rw [hx]; rcases hc with h | h <;> simp [h]
  have h1 := Finset.add_sum_erase Finset.univ (fun j => (x.1 j) ^ 2)
    (Finset.mem_univ (Fin.last (n + 1)))
  simp only [hsq, hlast] at h1
  have hi2 : (x.1 i) ^ 2 = 0 :=
    (Finset.sum_eq_zero_iff_of_nonneg (fun j _ => sq_nonneg (x.1 j))).mp (by linarith) i
      (Finset.mem_erase.mpr ⟨hi, Finset.mem_univ i⟩)
  exact (pow_eq_zero_iff two_ne_zero).mp hi2

/-- A unit-sphere point whose last coordinate equals `c = ±1` is the "pole" point with all other
coordinates zero, i.e. `x.1 = EuclideanSpace.single (Fin.last (n + 1)) c`. -/
theorem sphere_pole_coords_vanish (hc : c = 1 ∨ c = -1)
    (x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1)
    (hx : x.1 (Fin.last (n + 1)) = c) :
    (x.1 : EuclideanSpace ℝ (Fin (n + 2))) = EuclideanSpace.single (Fin.last (n + 1)) c := by
  have h_vanish := sphere_off_pole_coord_zero n c hc x hx
  ext i
  by_cases hi : i = Fin.last (n + 1)
  · subst hi
    rw [PiLp.single_apply]
    simp [hx]
  · rw [h_vanish i hi, PiLp.single_apply]
    simp [hi]

/-- On the unit sphere, having last coordinate `c = ±1` is equivalent to being the pole point
`EuclideanSpace.single (Fin.last (n + 1)) c`. -/
theorem sphere_pole_coord_eq (hc : c = 1 ∨ c = -1)
    (hmem : (EuclideanSpace.single (Fin.last (n + 1)) c : EuclideanSpace ℝ (Fin (n + 2)))
        ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1)
    (x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1) :
    x.1 (Fin.last (n + 1)) = c ↔ x = ⟨EuclideanSpace.single (Fin.last (n + 1)) c, hmem⟩ := by
  constructor
  · intro hx
    exact Subtype.ext (sphere_pole_coords_vanish n c hc x hx)
  · intro hx
    rw [hx]
    simp

/-- The polar cap `{x | x.1 (Fin.last (n + 1)) ≠ c}` (for `c = ±1`) equals the complement of the
singleton pole point in the unit sphere. -/
theorem cap_eq_compl_pole (hc : c = 1 ∨ c = -1)
    (hmem : (EuclideanSpace.single (Fin.last (n + 1)) c : EuclideanSpace ℝ (Fin (n + 2)))
        ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1) :
    {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
        x.1 (Fin.last (n + 1)) ≠ c}
      = ({⟨EuclideanSpace.single (Fin.last (n + 1)) c, hmem⟩}ᶜ :
          Set (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1)) := by
  ext x
  rw [Set.mem_compl_iff, Set.mem_singleton_iff, Set.mem_setOf_eq]
  exact not_congr (sphere_pole_coord_eq n c hc hmem x)

/-- Each polar cap of the unit sphere, obtained by removing the pole point with last coordinate
`c = ±1`, is contractible. -/
theorem pole_cap_contractible (hc : c = 1 ∨ c = -1) :
    ContractibleSpace
      ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
          x.1 (Fin.last (n + 1)) ≠ c} := by
  have hnorm : ‖(EuclideanSpace.single (Fin.last (n + 1)) c : EuclideanSpace ℝ (Fin (n + 2)))‖
      = 1 := by
    rcases hc with h | h <;> subst h <;> simp
  have hmem : (EuclideanSpace.single (Fin.last (n + 1)) c : EuclideanSpace ℝ (Fin (n + 2)))
      ∈ Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 := by
    rw [mem_sphere_zero_iff_norm]; exact hnorm
  have hset : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
        x.1 (Fin.last (n + 1)) ≠ c}
      = ({⟨EuclideanSpace.single (Fin.last (n + 1)) c, hmem⟩}ᶜ :
          Set (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1)) :=
    cap_eq_compl_pole n c hc hmem
  have hcontr : ContractibleSpace
      ↥({⟨EuclideanSpace.single (Fin.last (n + 1)) c, hmem⟩}ᶜ :
          Set (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1)) :=
    sphere_compl_point_contractible hnorm hmem
  exact @Homeomorph.contractibleSpace _ _ _ _ hcontr (Homeomorph.setCongr hset)

end PolarCaps

/-- **Contractibility of the polar caps**: the two caps of the sphere obtained by excluding a
coordinate pole, `x.1 (Fin.last (n + 1)) ≠ -1` and `x.1 (Fin.last (n + 1)) ≠ 1`, are both
contractible. -/
theorem sphere_cap_contractible (n : ℕ) :
    ContractibleSpace
        ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
            x.1 (Fin.last (n + 1)) ≠ -1} ∧
      ContractibleSpace
        ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
            x.1 (Fin.last (n + 1)) ≠ 1} := by
  exact ⟨pole_cap_contractible n (-1) (Or.inr rfl), pole_cap_contractible n 1 (Or.inl rfl)⟩

/-- The zeroth singular homology of the sphere `TopCat.sphere n` (`n ≥ 1`) with coefficients in a
ring `R` is isomorphic to `R`: since the sphere is path-connected, the augmentation map
`TopCat.singularHomology₀ε` is an isomorphism onto `ModuleCat.of R R`. -/
noncomputable def sphere_homology_zero {R : Type} [Ring R] (n : ℕ) (hn : 1 ≤ n) :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
        (ModuleCat.of R R)).obj (TopCat.sphere n) ≅ ModuleCat.of R R := by
  haveI := sphere_path_connected_space n hn
  exact CategoryTheory.asIso (TopCat.singularHomology₀ε (TopCat.sphere n) (ModuleCat.of R R))

end Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps
