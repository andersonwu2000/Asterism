import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_hotel_shift
import Problems.Geometry.banach_tarski.proofs.L_is_decomp_hilbert
import Problems.Geometry.banach_tarski.proofs.L_left_inv_hilbert
import Problems.Geometry.banach_tarski.proofs.L_map_source_hilbert
import Problems.Geometry.banach_tarski.proofs.L_map_target_hilbert
import Problems.Geometry.banach_tarski.proofs.L_right_inv_hilbert

namespace Problems.Geometry.banach_tarski

-- Abstract Hilbert-hotel: set T = ⋃ₙ ρⁿ''D ("hotel"), map f = ρ on T / id off T,
-- inverse g = ρ⁻¹ on T / id off T. f sends A onto A∖D (key set fact: ρ''T = T∖D).
-- f,g are abstracted as parameters with defining equations hf/hf'/hg/hg', so each
-- PartialEquiv law + IsDecompOn is a self-contained Builder sub-goal free of the
-- piecewise case-lambda. The combinator is Equidecomp.mk (PartialEquiv.mk …).
theorem s11467
    (A D : Set E) (ρ : E ≃ᵢ E)
    (hDA : D ⊆ A)
    (hρA : ∀ x ∈ A, ρ x ∈ A)
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
  have hTA : T ⊆ A := by
    rw [hTdef]; rintro x hx
    obtain ⟨n, hn⟩ := Set.mem_iUnion.mp hx
    obtain ⟨y, hy, rfl⟩ := hn
    clear hx
    induction n generalizing y with
    | zero => simpa using hDA (by simpa using hy)
    | succ k ih =>
        rw [pow_succ']
        exact hρA _ (ih y hy)
  have hshift : ρ '' T = T \ D := by rw [hTdef]; exact hotel_shift D ρ hdisj
  have hms : ∀ x ∈ A, f x ∈ A \ D := map_source_hilbert A D T ρ f hf hf' hDT hTA hshift
  have hmt : ∀ y ∈ A \ D, g y ∈ A := map_target_hilbert A D T ρ g hg hg' hDT hTA hshift
  have hli : ∀ x ∈ A, g (f x) = x := left_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hri : ∀ y ∈ A \ D, f (g y) = y := right_inv_hilbert A D T ρ f g hf hf' hg hg' hshift
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S := is_decomp_hilbert A T ρ f hf hf'
  exact ⟨Equidecomp.mk (PartialEquiv.mk f g A (A \ D) hms hmt hli hri) hdec, rfl, rfl⟩

end Problems.Geometry.banach_tarski
