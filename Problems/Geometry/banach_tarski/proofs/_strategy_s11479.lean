import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_map_source_hilbert
import Problems.Geometry.banach_tarski.proofs.L_map_target_hilbert
import Problems.Geometry.banach_tarski.proofs.L_left_inv_hilbert
import Problems.Geometry.banach_tarski.proofs.L_right_inv_hilbert
import Problems.Geometry.banach_tarski.proofs.L_is_decomp_hilbert
import Problems.Geometry.banach_tarski.proofs.L_hotel_shift
import Problems.Geometry.banach_tarski.proofs.L_orbit_tower_disjoint
import Problems.Geometry.banach_tarski.proofs.L_source_diff_eq_target
import Problems.Geometry.banach_tarski.proofs.L_tower_subset_source

namespace Problems.Geometry.banach_tarski

-- Hilbert-hotel absorption of the empty-word reps along the φ(of 1)⁻¹ tower.
-- ρ := φ(of 1)⁻¹; D := empty-word reps (head? = none); T := ⋃ₙ ρⁿ''D the orbit
-- tower; the piecewise map f (= ρ on T, id off T) bijects the source A onto A\D.
-- Concrete sub-goals: T ⊆ A (tower stays in source), orbits pairwise disjoint
-- (so hotel_shift gives ρ''T = T\D), and A\D = the b-block target.  The four
-- PartialEquiv laws + IsDecompOn come from the abstract proved Hilbert bricks.
theorem s11479
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)) (hφ : Function.Injective φ)
    (M : Set E)
    (hinv : ∀ (w : FreeGroup (Fin 2)) (x : E), x ∈ M → φ w • x ∈ M)
    (hfree : ∀ (w : FreeGroup (Fin 2)), w ≠ 1 → ∀ x ∈ M, φ w • x ≠ x)
    (rep : E → E) (wrd : E → FreeGroup (Fin 2))
    (hx : ∀ x ∈ M, x = φ (wrd x) • rep x)
    (hcoh : ∀ x ∈ M, ∀ w : FreeGroup (Fin 2),
        rep (φ w • x) = rep x ∧ wrd (φ w • x) = w * wrd x) :
    ∃ e : Equidecomp E (E ≃ᵢ E),
      e.source = {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0} ∧
      e.target = {x | x ∈ M ∧
          ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
           (FreeGroup.toWord (wrd x)).head? = some (1, false))}  := by
  classical
  set ρ : E ≃ᵢ E := (φ (FreeGroup.of 1))⁻¹ with hρ_def
  set D : Set E := {x | x ∈ M ∧ (FreeGroup.toWord (wrd x)).head? = none} with hD_def
  set A : Set E := {x | x ∈ M ∧ ¬ (FreeGroup.toWord (wrd x)).head?.map Prod.fst = some 0}
    with hA_def
  set T : Set E := ⋃ n : ℕ, (ρ ^ n) '' D with hT_def
  set f : E → E := fun x => if x ∈ T then ρ x else x with hf_def
  set g : E → E := fun y => if y ∈ T then ρ.symm y else y with hg_def
  -- defining equations of the piecewise maps
  have hf : ∀ x, x ∈ T → f x = ρ x := by intro x hx; rw [hf_def]; exact if_pos hx
  have hf' : ∀ x, x ∉ T → f x = x := by intro x hx; rw [hf_def]; exact if_neg hx
  have hg : ∀ y, y ∈ T → g y = ρ.symm y := by intro y hy; rw [hg_def]; exact if_pos hy
  have hg' : ∀ y, y ∉ T → g y = y := by intro y hy; rw [hg_def]; exact if_neg hy
  -- D at the base of the tower; tower lands in the source; orbits disjoint
  have hDT : D ⊆ T := by
    intro x hx; rw [hT_def]; exact Set.mem_iUnion.mpr ⟨0, x, hx, by simp⟩
  have hTA : T ⊆ A := tower_subset_source φ M hinv rep wrd hcoh
  have hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D)) :=
    orbit_tower_disjoint φ M hinv rep wrd hcoh
  have hshift : ρ '' T = T \ D := hotel_shift D ρ hdisj
  have hAD : A \ D = {x | x ∈ M ∧
      ((FreeGroup.toWord (wrd x)).head? = some (1, true) ∨
       (FreeGroup.toWord (wrd x)).head? = some (1, false))} := source_diff_eq_target M wrd
  -- the four PartialEquiv laws + IsDecompOn from the abstract Hilbert bricks
  have hms : ∀ x ∈ A, f x ∈ A \ D := map_source_hilbert A D T ρ f hf hf' hDT hTA hshift
  have hmt : ∀ y ∈ A \ D, g y ∈ A := map_target_hilbert A D T ρ g hg hg' hDT hTA hshift
  have hli : ∀ x ∈ A, g (f x) = x := left_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hri : ∀ y ∈ A \ D, f (g y) = y := right_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S :=
    is_decomp_hilbert A T ρ f hf hf'
  refine ⟨Equidecomp.mk (PartialEquiv.mk f g A (A \ D) hms hmt hli hri) hdec, rfl, ?_⟩
  exact hAD

end Problems.Geometry.banach_tarski
