import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Trans-glue of two origin-fixing equidecompositions: witness e := e₁.trans e₂,
-- realizing Finset S := S₂ ⋆ S₁ (Finset.image₂ (·*·)). Source/target come from the
-- PartialEquiv.trans laws; IsDecompOn from per-factor decomp + mul_smul; origin-fixing
-- since (g₂*g₁) 0 = g₂ (g₁ 0) = g₂ 0 = 0. Self-contained leaf.
theorem s11529
    (e₁ e₂ : Equidecomp E (E ≃ᵢ E)) (h : e₁.target = e₂.source)
    (S₁ S₂ : Finset (E ≃ᵢ E))
    (hd₁ : Equidecomp.IsDecompOn e₁.toFun e₁.source S₁)
    (hd₂ : Equidecomp.IsDecompOn e₂.toFun e₂.source S₂)
    (h0₁ : ∀ s ∈ S₁, s 0 = 0) (h0₂ : ∀ s ∈ S₂, s 0 = 0) :
    ∃ (e : Equidecomp E (E ≃ᵢ E)) (S : Finset (E ≃ᵢ E)),
      e.source = e₁.source ∧ e.target = e₂.target ∧
      Equidecomp.IsDecompOn e.toFun e.source S ∧
      (∀ s ∈ S, s 0 = 0)  := by
  classical
  refine ⟨e₁.trans e₂, Finset.image₂ (· * ·) S₂ S₁, ?_, ?_, ?_, ?_⟩
  · simp only [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_source]
    rw [← h]
    ext x
    simp only [Set.mem_inter_iff, Set.mem_preimage]
    constructor
    · intro ⟨hx, _⟩; exact hx
    · intro hx; exact ⟨hx, e₁.map_source' hx⟩
  · simp only [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_target]
    rw [h]
    ext x
    simp only [Set.mem_inter_iff, Set.mem_preimage]
    constructor
    · intro ⟨hx, _⟩; exact hx
    · intro hx; exact ⟨hx, e₂.map_target' hx⟩
  · intro a ha
    rw [Equidecomp.trans_toPartialEquiv, PartialEquiv.trans_source] at ha
    obtain ⟨ha1, ha2⟩ := ha
    obtain ⟨g₁, hg₁, hfa⟩ := hd₁ a ha1
    obtain ⟨g₂, hg₂, hfb⟩ := hd₂ (e₁.toFun a) ha2
    refine ⟨g₂ * g₁, Finset.mem_image₂_of_mem hg₂ hg₁, ?_⟩
    change e₂.toFun (e₁.toFun a) = (g₂ * g₁) • a
    rw [hfb, hfa, mul_smul]
  · intro s hs
    obtain ⟨g₂, hg₂, g₁, hg₁, rfl⟩ := Finset.mem_image₂.mp hs
    calc (g₂ * g₁) 0 = g₂ (g₁ 0) := rfl
      _ = g₂ 0 := by rw [h0₁ g₁ hg₁]
      _ = 0 := h0₂ g₂ hg₂

end Problems.Geometry.banach_tarski
