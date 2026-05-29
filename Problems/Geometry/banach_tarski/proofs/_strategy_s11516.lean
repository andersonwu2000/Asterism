import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Compose two origin-fixing decompositions through `Equidecomp.trans`.
-- Witness finset is the pointwise product `S₂ ⋆ S₁` (`Finset.image₂ (·*·)`): on the
-- trans-source, `e₁` acts as some `g₁ ∈ S₁` and `e₂` (at `e₁ a`) as some `g₂ ∈ S₂`, so
-- the composite acts as `(g₂*g₁)•a` by `mul_smul`; each product fixes 0 since
-- `(g₂*g₁) 0 = g₂ (g₁ 0) = g₂ 0 = 0`. Direct leaf — no sub-goals.
theorem s11516
    (e₁ e₂ : Equidecomp E (E ≃ᵢ E)) (S₁ S₂ : Finset (E ≃ᵢ E))
    (hd₁ : Equidecomp.IsDecompOn e₁.toFun e₁.source S₁)
    (hd₂ : Equidecomp.IsDecompOn e₂.toFun e₂.source S₂)
    (h0₁ : ∀ s ∈ S₁, s 0 = 0) (h0₂ : ∀ s ∈ S₂, s 0 = 0) :
    ∃ S : Finset (E ≃ᵢ E),
      Equidecomp.IsDecompOn (e₁.trans e₂).toFun (e₁.trans e₂).source S ∧
      (∀ s ∈ S, s 0 = 0)  := by
  classical
  refine ⟨Finset.image₂ (· * ·) S₂ S₁, ?_, ?_⟩
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
