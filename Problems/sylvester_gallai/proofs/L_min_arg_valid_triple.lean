import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
-- min_arg_valid_triple: extract a minimizer of f over valid (p,q,r) triples
-- via Finset.exists_min_image on a classically-filtered product Finset
theorem min_arg_valid_triple : ∀ (P : Finset (ℝ × ℝ))
    (f : (ℝ × ℝ) → (ℝ × ℝ) → (ℝ × ℝ) → ℝ),
    (∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r) →
    ∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r ∧
      ∀ p' ∈ P, ∀ q' ∈ P, ∀ r' ∈ P, p' ≠ q' → ¬ Collinear p' q' r' →
        f p q r ≤ f p' q' r' := by
  intro P f ⟨p₀, hp₀, q₀, hq₀, r₀, hr₀, hneq₀, hncol₀⟩
  classical
  let S := (P ×ˢ (P ×ˢ P)).filter
    (fun t : (ℝ × ℝ) × (ℝ × ℝ) × (ℝ × ℝ) => t.1 ≠ t.2.1 ∧ ¬ Collinear t.1 t.2.1 t.2.2)
  have hS : S.Nonempty :=
    ⟨(p₀, q₀, r₀), Finset.mem_filter.mpr ⟨Finset.mem_product.mpr
      ⟨hp₀, Finset.mem_product.mpr ⟨hq₀, hr₀⟩⟩, hneq₀, hncol₀⟩⟩
  obtain ⟨⟨p, q, r⟩, hmem, hmin⟩ := S.exists_min_image (fun t => f t.1 t.2.1 t.2.2) hS
  rw [Finset.mem_filter, Finset.mem_product, Finset.mem_product] at hmem
  obtain ⟨⟨hp, hq, hr⟩, hneq, hncol⟩ := hmem
  exact ⟨p, hp, q, hq, r, hr, hneq, hncol, fun p' hp' q' hq' r' hr' hneq' hncol' =>
    hmin (p', q', r') (Finset.mem_filter.mpr ⟨Finset.mem_product.mpr
      ⟨hp', Finset.mem_product.mpr ⟨hq', hr'⟩⟩, hneq', hncol'⟩)⟩

end Problems.sylvester_gallai
