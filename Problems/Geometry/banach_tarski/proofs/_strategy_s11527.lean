import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_map_source_hilbert
import Problems.Geometry.banach_tarski.proofs.L_map_target_hilbert
import Problems.Geometry.banach_tarski.proofs.L_left_inv_hilbert
import Problems.Geometry.banach_tarski.proofs.L_right_inv_hilbert
import Problems.Geometry.banach_tarski.proofs.L_hotel_shift
import Problems.Geometry.banach_tarski.proofs.L_orbit_tower_disjoint
import Problems.Geometry.banach_tarski.proofs.L_source_diff_eq_target
import Problems.Geometry.banach_tarski.proofs.L_tower_subset_source
import Problems.Geometry.banach_tarski.proofs.L_is_decomp_hilbert_origin_fixing_2

namespace Problems.Geometry.banach_tarski

-- Origin-fixing mirror of absorb_empty_word (s11479): same Hilbert-hotel piecewise
-- map f (ρ := φ(of 1)⁻¹ on the orbit tower T, id off T) realizing source ≃ source\D,
-- but now ALSO expose the realizing Finset {ρ,1} and prove every member fixes 0.
-- The four PartialEquiv laws + the tower/disjoint/shift facts are the proved Hilbert
-- bricks (cited inline); the ONLY new sub-goal is is_decomp_hilbert_origin_fixing_2, which
-- packages the {ρ,1} witness together with ρ 0 = 0 (and 1 0 = 0).  ρ 0 = 0 holds
-- because ρ = φ((of 1)⁻¹) and hfix0 fixes the origin for every φ-image.
theorem s11527
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ (e : Equidecomp E (E ≃ᵢ E)) (Sa : Finset (E ≃ᵢ E)),
      e.source = {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} ∧
      e.target = {x | x ∈ M ∧
          ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
           (FreeGroup.toWord (wrd x)).head? = some (1, false))} ∧
      Equidecomp.IsDecompOn e.toFun e.source Sa ∧
      (∀ s ∈ Sa, s 0 = 0)  := by
  classical
  set ρ : E ≃ᵢ E := (φ (FreeGroup.of 1))⁻¹ with hρ_def
  set D : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none} with hD_def
  set A : Set E := {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0}
    with hA_def
  set T : Set E := ⋃ n : ℕ, (ρ ^ n) '' D with hT_def
  set f : E → E := fun x => if x ∈ T then ρ x else x with hf_def
  set g : E → E := fun y => if y ∈ T then ρ.symm y else y with hg_def
  have hf : ∀ x, x ∈ T → f x = ρ x := by intro x hx; rw [hf_def]; exact if_pos hx
  have hf' : ∀ x, x ∉ T → f x = x := by intro x hx; rw [hf_def]; exact if_neg hx
  have hg : ∀ y, y ∈ T → g y = ρ.symm y := by intro y hy; rw [hg_def]; exact if_pos hy
  have hg' : ∀ y, y ∉ T → g y = y := by intro y hy; rw [hg_def]; exact if_neg hy
  have hDT : D ⊆ T := by
    intro x hx; rw [hT_def]; exact Set.mem_iUnion.mpr ⟨0, x, hx, by simp⟩
  have hTA : T ⊆ A := tower_subset_source φ M hinv rep wrd hcoh
  have hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D)) :=
    orbit_tower_disjoint φ M hinv rep wrd hcoh
  have hshift : ρ '' T = T \ D := hotel_shift D ρ hdisj
  have hAD : A \ D = {x | x ∈ M ∧
      ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
       (FreeGroup.toWord (wrd x)).head? = some (1, false))} := source_diff_eq_target M wrd
  have hms : ∀ x ∈ A, f x ∈ A \ D := map_source_hilbert A D T ρ f hf hf' hDT hTA hshift
  have hmt : ∀ y ∈ A \ D, g y ∈ A := map_target_hilbert A D T ρ g hg hg' hDT hTA hshift
  have hli : ∀ x ∈ A, g (f x) = x := left_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hri : ∀ y ∈ A \ D, f (g y) = y := right_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hρ0 : ρ 0 = 0 := by
    have heq : ρ = φ ((FreeGroup.of 1)⁻¹) := by rw [hρ_def, map_inv]
    rw [heq]; exact hfix0 _
  obtain ⟨S, hSdec, hSfix⟩ := is_decomp_hilbert_origin_fixing_2 A T ρ f hf hf' hρ0
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g A (A \ D) hms hmt hli hri) ⟨S, hSdec⟩,
    S, rfl, hAD, hSdec, hSfix⟩

end Problems.Geometry.banach_tarski
