import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_exists_rotation_pairwise_disjoint_orbit_off_origin
import Problems.Geometry.banach_tarski.proofs.L_hotel_shift
import Problems.Geometry.banach_tarski.proofs.L_map_source_hilbert
import Problems.Geometry.banach_tarski.proofs.L_map_target_hilbert
import Problems.Geometry.banach_tarski.proofs.L_left_inv_hilbert
import Problems.Geometry.banach_tarski.proofs.L_right_inv_hilbert
import Problems.Geometry.banach_tarski.proofs.L_hotel_subset_sphere
import Problems.Geometry.banach_tarski.proofs.L_is_decomp_hilbert_origin_fixing

namespace Problems.Geometry.banach_tarski

-- Origin-fixing Hilbert-hotel absorption S² ≃ S²∖D, exposing origin-fixing decomp data.
-- Pick a rotation ρ fixing 0 with pairwise-disjoint orbits ρⁿ''D (proved sibling
-- exists_rotation_pairwise_disjoint_orbit_off_origin); build the piecewise hotel map
-- f = ρ on T = ⋃ₙ ρⁿ''D / id off T, g = ρ.symm on T / id off T, and assemble the
-- Equidecomp from the proved abstract bricks map_source/target_hilbert + left/right_inv_hilbert
-- (4 PartialEquiv laws) with hotel_shift (ρ''T = T∖D). Two strictly-simpler NEW sub-goals:
--   • hotel_subset_sphere — the orbit tower T stays on S² (ρⁿ fix 0, isometry preserves sphere);
--   • is_decomp_hilbert_origin_fixing — IsDecompOn with witness set {ρ,1} ALL FIXING 0, the
--     origin-fixing strengthening of the proved is_decomp_hilbert; reused for both h (via ρ)
--     and h.symm (via ρ.symm, which fixes 0 too).  Both sub-goals drop the equidecomp layer.
theorem s11511
    (D : Set E) (hDc : D.Countable) (hDs : D ⊆ Metric.sphere (0 : E) 1)
    (hD0 : (0 : E) ∉ D) :
    ∃ (h : Equidecomp E (E ≃ᵢ E)) (Sh Sh' : Finset (E ≃ᵢ E)),
      h.source = Metric.sphere (0 : E) 1 ∧
      h.target = Metric.sphere (0 : E) 1 \ D ∧
      Equidecomp.IsDecompOn h.toFun h.source Sh ∧
      Equidecomp.IsDecompOn h.symm.toFun h.symm.source Sh' ∧
      (∀ s ∈ Sh, s 0 = 0) ∧ (∀ s ∈ Sh', s 0 = 0)  := by
  classical
  obtain ⟨ρ, hρ0, hdisj⟩ := exists_rotation_pairwise_disjoint_orbit_off_origin D hDc hD0
  set T : Set E := ⋃ n : ℕ, (ρ ^ n) '' D with hTdef
  set f : E → E := fun x => if x ∈ T then ρ x else x with hf_def
  set g : E → E := fun y => if y ∈ T then ρ.symm y else y with hg_def
  have hf : ∀ x, x ∈ T → f x = ρ x := by intro x hx; rw [hf_def]; exact if_pos hx
  have hf' : ∀ x, x ∉ T → f x = x := by intro x hx; rw [hf_def]; exact if_neg hx
  have hg : ∀ y, y ∈ T → g y = ρ.symm y := by intro y hy; rw [hg_def]; exact if_pos hy
  have hg' : ∀ y, y ∉ T → g y = y := by intro y hy; rw [hg_def]; exact if_neg hy
  have hshift : ρ '' T = T \ D := hotel_shift D ρ hdisj
  have hDT : D ⊆ T := fun x hx => Set.mem_iUnion.mpr ⟨0, by simpa using hx⟩
  have hTA : T ⊆ Metric.sphere (0 : E) 1 := hotel_subset_sphere D ρ hρ0 hDs
  have hms := map_source_hilbert (Metric.sphere (0 : E) 1) D T ρ f hf hf' hDT hTA hshift
  have hmt := map_target_hilbert (Metric.sphere (0 : E) 1) D T ρ g hg hg' hDT hTA hshift
  have hli := left_inv_hilbert (Metric.sphere (0 : E) 1) D T ρ f g hf hf' hg hg' hshift
  have hri := right_inv_hilbert (Metric.sphere (0 : E) 1) D T ρ f g hf hf' hg hg' hshift
  obtain ⟨Sh, hSh, hSh0⟩ :=
    is_decomp_hilbert_origin_fixing (Metric.sphere (0 : E) 1) T ρ hρ0 f hf hf'
  have hρ0' : ρ.symm 0 = 0 := by
    have := ρ.symm_apply_apply 0; rwa [hρ0] at this
  obtain ⟨Sh', hSh', hSh'0⟩ :=
    is_decomp_hilbert_origin_fixing (Metric.sphere (0 : E) 1 \ D) T ρ.symm hρ0' g hg hg'
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g (Metric.sphere (0 : E) 1)
      (Metric.sphere (0 : E) 1 \ D) hms hmt hli hri) ⟨Sh, hSh⟩, Sh, Sh', rfl, rfl,
    hSh, hSh', hSh0, hSh'0⟩

end Problems.Geometry.banach_tarski
