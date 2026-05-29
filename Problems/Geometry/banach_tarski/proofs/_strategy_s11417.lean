import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- The fixed-point set in s is the union over nontrivial g of each g's fixed set.
-- {g | g ≠ 1} is countable (G countable); each fiber is finite (hfin) hence
-- countable; Set.Countable.biUnion closes it directly — no sub-goals needed.
theorem s11417
    {G : Type*} [Group G] [Countable G] {X : Type*} [MulAction G X]
    (s : Set X)
    (hfin : ∀ g : G, g ≠ 1 → {x ∈ s | g • x = x}.Finite) :
    {x ∈ s | ∃ g : G, g ≠ 1 ∧ g • x = x}.Countable  := by
  have hset : {x ∈ s | ∃ g : G, g ≠ 1 ∧ g • x = x}
      = ⋃ g ∈ {g : G | g ≠ 1}, {x ∈ s | g • x = x} := by
    ext x
    simp only [Set.mem_setOf_eq, Set.mem_iUnion]
    constructor
    · rintro ⟨hx, g, hg, hgx⟩; exact ⟨g, hg, hx, hgx⟩
    · rintro ⟨g, hg, hx, hgx⟩; exact ⟨hx, g, hg, hgx⟩
  rw [hset]
  apply Set.Countable.biUnion (Set.to_countable _)
  intro g hg
  exact (hfin g hg).countable

end Problems.Geometry.banach_tarski
