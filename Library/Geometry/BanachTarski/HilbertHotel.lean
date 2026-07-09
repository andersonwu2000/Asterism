import Mathlib.Algebra.Group.Action.Equidecomp
import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Mathlib.Order.BourbakiWitt
import Mathlib.Order.CompletePartialOrder
import Library.Geometry.BanachTarski.Defs

/-!
# Hilbert's Hotel for the Banach–Tarski paradox

Auxiliary lemmas that formalise the *Hilbert-hotel shift*: given a set `D ⊆ A` whose
`ρ`-orbit `T = ⋃ₙ ρⁿ(D)` still lies in `A` and whose pieces are pairwise disjoint, there
is an equidecomposition sending `A` to `A \ D`.  This is the key combinatorial step used
in the Banach–Tarski construction.

## Main statements

- `hotel_shift`: applying `ρ` to the hotel `T = ⋃ₙ ρⁿ(D)` shifts it to `T \ D`.
- `relaxed_hilbert_hotel`: produces an `Equidecomp E (E ≃ᵢ E)` with source `A` and
  target `A \ D`, given that the orbit of `D` under `ρ` is pairwise disjoint and contained
  in `A`.

## Implementation notes

The "relaxed" variant does not require `ρ` to preserve `A`; instead it asks directly that
the orbit `T ⊆ A`.  The equidecomposition witness uses `f = ρ` on `T` and `f = id` off
`T`, with inverse `g = ρ⁻¹` on `T` and `g = id` off `T`.
-/

open Library.Geometry.BanachTarski.Defs

namespace Library.Geometry.BanachTarski.HilbertHotel

/-- The image of the orbit union `⋃ₙ ρⁿ(D)` under `ρ` is the shifted union `⋃ₙ ρⁿ⁺¹(D)`. -/
theorem shift_image (D : Set E) (ρ : E ≃ᵢ E) :
    ρ '' (⋃ n : ℕ, (ρ ^ n) '' D) = ⋃ n : ℕ, (ρ ^ (n+1)) '' D := by
  simp only [Set.image_iUnion]
  congr 1; ext n
  rw [Set.image_image]
  have : ρ ^ (n + 1) = ρ * ρ ^ n := by
    rw [show n + 1 = 1 + n from by omega, pow_add, pow_one]
  rw [this]; rfl

/-- The tail union `⋃ₙ ρⁿ⁺¹(D)` equals `(⋃ₙ ρⁿ(D)) \ D` when the orbit pieces are
pairwise disjoint.  The key point is that `ρ⁰(D) = D` is disjoint from every `ρⁿ⁺¹(D)`,
so any element of the shifted union cannot belong to `D`. -/
theorem tail_eq (D : Set E) (ρ : E ≃ᵢ E)
    (hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))) :
    (⋃ n : ℕ, (ρ ^ (n+1)) '' D) = (⋃ n : ℕ, (ρ ^ n) '' D) \ D := by
  have hD0 : (ρ ^ (0:ℕ)) '' D = D := by simp
  ext x
  simp only [Set.mem_iUnion, Set.mem_diff]
  constructor
  · rintro ⟨n, hn⟩
    refine ⟨⟨n+1, hn⟩, ?_⟩
    intro hxD
    have h0 : x ∈ (ρ ^ (0:ℕ)) '' D := by rw [hD0]; exact hxD
    exact (hdisj (by omega : (0:ℕ) ≠ n+1)).le_bot ⟨h0, hn⟩
  · rintro ⟨⟨n, hn⟩, hxD⟩
    cases n with
    | zero => rw [hD0] at hn; exact absurd hn hxD
    | succ m => exact ⟨m, hn⟩

/-- Applying `ρ` to the hotel `T = ⋃ₙ ρⁿ(D)` shifts it to `T \ D`, provided the orbit
pieces are pairwise disjoint.  This is the central set-algebraic identity: the shift
`ρ(T) = ⋃ₙ ρⁿ⁺¹(D)` (by `shift_image`) equals `T \ D` (by `tail_eq`). -/
theorem hotel_shift (D : Set E) (ρ : E ≃ᵢ E)
    (hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))) :
    ρ '' (⋃ n : ℕ, (ρ ^ n) '' D) = (⋃ n : ℕ, (ρ ^ n) '' D) \ D := by
  have h_shift := shift_image D ρ
  have h_tail := tail_eq D ρ hdisj
  rw [h_shift, h_tail]

/-- A function `f` that acts as the isometry `ρ` on a set `T` and as the identity off `T`
satisfies `Equidecomp.IsDecompOn f A {ρ, 1}` for any ambient set `A`. -/
theorem is_decomp_hilbert (A T : Set E) (ρ : E ≃ᵢ E) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x) :
    ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S := by
  haveI : DecidableEq (E ≃ᵢ E) := Classical.decEq _
  refine ⟨{ρ, 1}, fun a _ => ?_⟩
  by_cases hT : a ∈ T
  · exact ⟨ρ, Finset.mem_insert_self ρ {1}, hf a hT⟩
  · exact ⟨1, Finset.mem_insert.mpr (Or.inr (Finset.mem_singleton.mpr rfl)),
      by rw [hf' a hT]; rfl⟩

/-- Left inverse of the hotel map: if `f = ρ` on `T` and `f = id` off `T`, and `g = ρ⁻¹`
on `T` and `g = id` off `T`, and `ρ(T) = T \ D`, then `g ∘ f = id` on `A`. -/
theorem left_inv_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (f g : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x)
    (hg : ∀ y, y ∈ T → g y = ρ.symm y) (hg' : ∀ y, y ∉ T → g y = y)
    (hshift : ρ '' T = T \ D) :
    ∀ x ∈ A, g (f x) = x := by
  intro x _
  by_cases hxT : x ∈ T
  · rw [hf x hxT]
    have hρxT : ρ x ∈ T := by
      have hmem : ρ x ∈ ρ '' T := Set.mem_image_of_mem _ hxT
      rw [hshift] at hmem
      exact hmem.1
    rw [hg (ρ x) hρxT]
    exact ρ.symm_apply_apply x
  · rw [hf' x hxT, hg' x hxT]

/-- Map source: the hotel map `f` (equal to `ρ` on `T`, identity off `T`) sends every
point of `A` into `A \ D`, given `D ⊆ T ⊆ A` and `ρ(T) = T \ D`. -/
theorem map_source_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x)
    (hDT : D ⊆ T) (hTA : T ⊆ A) (hshift : ρ '' T = T \ D) :
    ∀ x ∈ A, f x ∈ A \ D := by
  intro x hxA
  by_cases hxT : x ∈ T
  · rw [hf x hxT]
    have hmem : ρ x ∈ ρ '' T := Set.mem_image_of_mem _ hxT
    rw [hshift] at hmem
    exact ⟨hTA hmem.1, hmem.2⟩
  · rw [hf' x hxT]
    exact ⟨hxA, fun hxD => hxT (hDT hxD)⟩

/-- Map target: the inverse map `g` (equal to `ρ⁻¹` on `T`, identity off `T`) sends every
point of `A \ D` back into `A`, given `D ⊆ T ⊆ A` and `ρ(T) = T \ D`. -/
theorem map_target_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (g : E → E)
    (hg : ∀ y, y ∈ T → g y = ρ.symm y) (hg' : ∀ y, y ∉ T → g y = y)
    (_hDT : D ⊆ T) (hTA : T ⊆ A) (hshift : ρ '' T = T \ D) :
    ∀ y ∈ A \ D, g y ∈ A := by
  intro y ⟨hyA, hyD⟩
  by_cases hyT : y ∈ T
  · rw [hg y hyT]
    have hy_shift : y ∈ ρ '' T := by rw [hshift]; exact ⟨hyT, hyD⟩
    obtain ⟨z, hz, hρz⟩ := hy_shift
    rw [← hρz, IsometryEquiv.symm_apply_apply]
    exact hTA hz
  · rw [hg' y hyT]; exact hyA

/-- Right inverse of the hotel map: if `f = ρ` on `T` and `f = id` off `T`, and `g = ρ⁻¹`
on `T` and `g = id` off `T`, and `ρ(T) = T \ D`, then `f ∘ g = id` on `A \ D`. -/
theorem right_inv_hilbert (A D T : Set E) (ρ : E ≃ᵢ E) (f g : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x)
    (hg : ∀ y, y ∈ T → g y = ρ.symm y) (hg' : ∀ y, y ∉ T → g y = y)
    (hshift : ρ '' T = T \ D) :
    ∀ y ∈ A \ D, f (g y) = y := by
  intro y hy
  simp only [Set.mem_diff] at hy
  obtain ⟨_, hyD⟩ := hy
  by_cases hyT : y ∈ T
  · have hgyT : ρ.symm y ∈ T := by
      have hy_in : y ∈ ρ '' T := by rw [hshift]; exact ⟨hyT, hyD⟩
      obtain ⟨x, hxT, hρxy⟩ := hy_in
      rwa [← hρxy, IsometryEquiv.symm_apply_apply]
    rw [hg y hyT, hf (ρ.symm y) hgyT, IsometryEquiv.apply_symm_apply]
  · rw [hg' y hyT, hf' y hyT]

/-- **Relaxed Hilbert's Hotel**: given a set `D ⊆ A` whose `ρ`-orbit `T = ⋃ₙ ρⁿ(D)` lies
in `A` and whose pieces are pairwise disjoint, there exists an equidecomposition
`h : Equidecomp E (E ≃ᵢ E)` satisfying `h.source = A` and `h.target = A \ D`.

This is the "relaxed" variant: unlike the invariant version, it does not require `ρ` to
map `A` into itself — it only requires the orbit of `D` to be contained in `A`.  The
equidecomposition is witnessed by `f = ρ` on `T` and `f = id` off `T`. -/
theorem relaxed_hilbert_hotel (A D : Set E) (ρ : E ≃ᵢ E)
    (_hDA : D ⊆ A)
    (hTA : (⋃ n : ℕ, (ρ ^ n) '' D) ⊆ A)
    (hdisj : Pairwise (fun i j : ℕ => Disjoint ((ρ ^ i) '' D) ((ρ ^ j) '' D))) :
    ∃ h : Equidecomp E (E ≃ᵢ E), h.source = A ∧ h.target = A \ D := by
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
  have hdec : ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S :=
    is_decomp_hilbert A T ρ f hf hf'
  exact ⟨Equidecomp.mk (PartialEquiv.mk f g A (A \ D) hms hmt hli hri) hdec, rfl, rfl⟩

end Library.Geometry.BanachTarski.HilbertHotel
