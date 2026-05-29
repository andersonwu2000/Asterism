import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct proof (leaf-bypass): a cosine level set {t | cos t = c} is countable.
-- Case-split on ∃ t₀, cos t₀ = c. If none, the set is empty. Otherwise
-- `Real.cos_eq_cos_iff` shows every solution t equals 2kπ ± t₀ for some k : ℤ,
-- so the set sits inside the union of two ℤ-indexed ranges (countable), and
-- `Set.Countable.mono` transports countability back.
theorem s11466 (c : ℝ) :
    {t : ℝ | Real.cos t = c}.Countable  := by
  by_cases h : ∃ t₀ : ℝ, Real.cos t₀ = c
  · obtain ⟨t₀, ht₀⟩ := h
    have hcount :
        ((Set.range (fun k : ℤ => 2 * (k : ℝ) * Real.pi + t₀)) ∪
          (Set.range (fun k : ℤ => 2 * (k : ℝ) * Real.pi - t₀))).Countable :=
      (Set.countable_range _).union (Set.countable_range _)
    apply hcount.mono
    intro t ht
    simp only [Set.mem_setOf_eq] at ht
    have hcc : Real.cos t₀ = Real.cos t := by rw [ht₀, ht]
    rw [Real.cos_eq_cos_iff] at hcc
    obtain ⟨k, hk | hk⟩ := hcc
    · exact Or.inl ⟨k, hk.symm⟩
    · exact Or.inr ⟨k, hk.symm⟩
  · simp only [not_exists] at h
    have he : {t : ℝ | Real.cos t = c} = ∅ := by
      ext t
      simp only [Set.mem_setOf_eq, Set.mem_empty_iff_false, iff_false]
      exact h t
    rw [he]
    exact Set.countable_empty

end Problems.Geometry.banach_tarski
