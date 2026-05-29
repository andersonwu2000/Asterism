import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_isometry_fixed_complement_invariant
import Problems.Geometry.banach_tarski.proofs.L_det_eq_prod_det_restrict_invariant
import Problems.Geometry.banach_tarski.proofs.L_det_one_isometry_finrank_le_one_submodule_eq_id

namespace Problems.Geometry.banach_tarski

-- Contrapositive route: assume `1 < finrank V` (V = ker(T-id), the fixed subspace).
-- V is T-invariant; so is its orthogonal complement Vᗮ (s11421). det T splits as
-- det(T|V)·det(T|Vᗮ) (s11422); det(T|V)=1 (T is id on V) and det T = 1 give det(T|Vᗮ)=1.
-- finrank V ≥ 2 ⇒ finrank Vᗮ ≤ 1, so the det-1 isometry T|Vᗮ is id (s11427), i.e. T fixes Vᗮ.
-- That collapses to T = refl (Vᗮ ⊆ V ∩ Vᗮ = 0 ⇒ Vᗮ = 0 ⇒ V = ⊤), contradicting hne.
theorem s11428
    (T : E ≃ₗᵢ[ℝ] E)
    (hdet : LinearMap.det (T.toLinearEquiv.toLinearMap) = 1)
    (hne : T ≠ LinearIsometryEquiv.refl ℝ E) :
    Module.finrank ℝ (LinearMap.ker (T.toLinearEquiv.toLinearMap - LinearMap.id)) ≤ 1  := by
  set L := T.toLinearEquiv.toLinearMap with hL
  -- `x` is fixed by `T` iff it lies in the kernel of `L - id`.
  have hmem : ∀ x : E, x ∈ LinearMap.ker (L - LinearMap.id) ↔ T x = x := by
    intro x
    rw [LinearMap.mem_ker, LinearMap.sub_apply, LinearMap.id_apply, sub_eq_zero]
    constructor <;> intro h <;> simpa [hL] using h
  by_contra hcon
  rw [not_le] at hcon
  set V := LinearMap.ker (L - LinearMap.id) with hV
  -- (1) the fixed subspace is `T`-invariant (in fact `T` acts as the identity on it).
  have hVinv : ∀ x ∈ V, T x ∈ V := by
    intro x hx
    rw [(hmem x).mp hx]
    exact hx
  -- (2) its orthogonal complement is `T`-invariant (proved sibling s11421).
  have hPinv : ∀ x ∈ Vᗮ, T x ∈ Vᗮ := isometry_fixed_complement_invariant T V hVinv
  have hbot : V ⊓ Vᗮ = ⊥ := Submodule.inf_orthogonal_eq_bot V
  have htop : V ⊔ Vᗮ = ⊤ := Submodule.sup_orthogonal_of_hasOrthogonalProjection
  -- (3) determinant splits over the invariant decomposition (proved sibling s11422).
  have hsplit := det_eq_prod_det_restrict_invariant L V Vᗮ hVinv hPinv hbot htop
  -- (4) `T` is the identity on `V`, so `det (T|V) = 1`.
  have hdetV : LinearMap.det (L.restrict hVinv) = 1 := by
    have hid : L.restrict hVinv = LinearMap.id := by
      refine LinearMap.ext fun y => ?_
      apply Subtype.ext
      have hy : T (y : E) = (y : E) := (hmem _).mp y.2
      simp only [LinearMap.restrict_apply, LinearMap.id_coe, id_eq]
      simpa [hL] using hy
    rw [hid, LinearMap.det_id]
  -- (5) hence `det (T|Vᗮ) = 1`.
  have hdetP : LinearMap.det (L.restrict hPinv) = 1 := by
    rw [hdetV, hdet] at hsplit; linarith
  -- (6) `finrank V ≥ 2` forces `finrank Vᗮ ≤ 1` in `ℝ³`.
  have hPle : Module.finrank ℝ (Vᗮ) ≤ 1 := by
    have hadd := Submodule.finrank_add_finrank_orthogonal (K := V)
    have h3 : Module.finrank ℝ E = 3 := finrank_euclideanSpace_fin
    omega
  -- (7) a det-1 isometry on a ≤1-dim invariant subspace is the identity (proved sibling s11427).
  have hfix : ∀ x ∈ Vᗮ, T x = x :=
    det_one_isometry_finrank_le_one_submodule_eq_id T Vᗮ hPinv hPle hdetP
  -- (8) collapse: `Vᗮ` is fixed ⇒ `Vᗮ ≤ V`, but `V ⊓ Vᗮ = ⊥`, so `Vᗮ = ⊥` and `V = ⊤`.
  have hsub : Vᗮ ≤ V := fun x hx => (hmem x).mpr (hfix x hx)
  have hVperp_bot : Vᗮ = ⊥ := by
    rw [eq_bot_iff, ← hbot]
    exact le_inf hsub le_rfl
  have hVtop : V = ⊤ := Submodule.orthogonal_eq_bot_iff.mp hVperp_bot
  -- (9) `T` then fixes every vector, i.e. `T = refl`, contradicting `hne`.
  apply hne
  refine LinearIsometryEquiv.ext (fun x => ?_)
  have hxV : x ∈ V := by rw [hVtop]; exact Submodule.mem_top
  rw [(hmem x).mp hxV]
  rfl

end Problems.Geometry.banach_tarski

