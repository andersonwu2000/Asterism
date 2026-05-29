import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_hotel_shift
import Problems.Geometry.banach_tarski.proofs.L_is_decomp_hilbert
import Problems.Geometry.banach_tarski.proofs.L_left_inv_hilbert
import Problems.Geometry.banach_tarski.proofs.L_map_source_hilbert
import Problems.Geometry.banach_tarski.proofs.L_map_target_hilbert
import Problems.Geometry.banach_tarski.proofs.L_right_inv_hilbert

namespace Problems.Geometry.banach_tarski

-- Relaxed Hilbert-hotel: same construction as the invariant version (s11467), but
-- T ⊆ A is supplied directly (hTA) instead of derived from ∀x∈A, ρx∈A — letting an
-- off-origin ρ (which maps closedBall 0 1 outside A) absorb D = {0}.
-- f = ρ on T = ⋃ₙ ρⁿ''D / id off T, inverse g = ρ⁻¹ on T / id off T; the 4
-- PartialEquiv laws + IsDecompOn are the proved abstract bricks, glued by Equidecomp.mk.
theorem s11505 (A D : Set E) (ρ : E ≃ᵢ E)
    (hDA : D ⊆ A)
    (hTA : (⋃ n : ℕ, (ρ ^ n) '' D) ⊆ A)
    (hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))) :
    ∃ h : Equidecomp E (E ≃ᵢ E), h.source = A ∧ h.target = A \ D  := by
  classical
  set T : Set E := ⋃ n : ℕ, (ρ ^ n) '' D with hTdef
  set f : E → E := fun x => if x ∈ T then ρ x else x with hfdef
  set g : E → E := fun y => if y ∈ T then ρ.symm y else y with hgdef
  have hf : ∀ x, x ∈ T → f x = ρ x := fun x hx => by simp [hfdef, hx]
  have hf' : ∀ x, x ∉ T → f x = x := fun x hx => by simp [hfdef, hx]
  have hg : ∀ y, y ∈ T → g y = ρ.symm y := fun y hy => by simp [hgdef, hy]
  have hg' : ∀ y, y ∉ T → g y = y := fun y hy => by simp [hgdef, hy]
  have hDT : D ⊆ T := by
    intro x hx
    rw [hTdef]; exact Set.mem_iUnion.mpr ⟨0, by simpa using hx⟩
  have hshift : ρ '' T = T \ D := by rw [hTdef]; exact hotel_shift D ρ hdisj
  have hms : ∀ x ∈ A, f x ∈ A \ D := map_source_hilbert A D T ρ f hf hf' hDT hTA hshift
  have hmt : ∀ y ∈ A \ D, g y ∈ A := map_target_hilbert A D T ρ g hg hg' hDT hTA hshift
  have hli : ∀ x ∈ A, g (f x) = x := left_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hri : ∀ y ∈ A \ D, f (g y) = y := right_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S := is_decomp_hilbert A T ρ f hf hf'
  exact ⟨Equidecomp.mk (PartialEquiv.mk f g A (A \ D) hms hmt hli hri) hdec, rfl, rfl⟩

end Problems.Geometry.banach_tarski
