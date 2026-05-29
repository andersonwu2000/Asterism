import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- cone_distrib_union: the radial cone distributes over set unions (pure set algebra)
theorem cone_distrib_union (A B : Set E) :
    {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ A ∪ B, y = r • x}
      = {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ A, y = r • x}
        ∪ {y | ∃ r ∈ Set.Ioc (0 : ℝ) 1, ∃ x ∈ B, y = r • x} := by
  ext y
  simp only [Set.mem_setOf_eq, Set.mem_union]
  constructor
  · rintro ⟨r, hr, x, hx | hx, hy⟩
    · left; exact ⟨r, hr, x, hx, hy⟩
    · right; exact ⟨r, hr, x, hx, hy⟩
  · rintro (⟨r, hr, x, hx, hy⟩ | ⟨r, hr, x, hx, hy⟩)
    · exact ⟨r, hr, x, Or.inl hx, hy⟩
    · exact ⟨r, hr, x, Or.inr hx, hy⟩

end Problems.Geometry.banach_tarski
