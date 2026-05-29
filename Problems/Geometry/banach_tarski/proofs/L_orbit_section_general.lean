import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- orbit_section_general: pure choice-axiom orbit section for any MulAction —
-- uses Quotient.out on orbitRel to pick canonical reps constant on orbits
theorem orbit_section_general {G : Type*} [Group G] {α : Type*} [MulAction G α] :
    ∃ (rep : α → α) (wrd : α → G),
      (∀ x, wrd x • rep x = x) ∧
      (∀ x (w : G), rep (w • x) = rep x) := by
  classical
  let setoid := MulAction.orbitRel G α
  let rep : α → α := fun x => (Quotient.mk' (s := setoid) x).out
  have hmem : ∀ x : α, ∃ g : G, g • rep x = x := by
    intro x
    have heq : (Quotient.mk' (s := setoid) (rep x)) = Quotient.mk' x := Quotient.out_eq _
    rw [Quotient.eq'] at heq
    -- heq : ∃ g, g • x = rep x
    obtain ⟨g, hg⟩ := heq
    exact ⟨g⁻¹, by rw [← hg, inv_smul_smul]⟩
  have hrep : ∀ (x : α) (w : G), rep (w • x) = rep x := by
    intro x w
    simp only [rep]
    congr 1
    apply Quotient.sound
    simp only [MulAction.orbitRel_apply]
    exact MulAction.mem_orbit x w
  refine ⟨rep, fun x => (hmem x).choose, ?_, hrep⟩
  exact fun x => (hmem x).choose_spec

end Problems.Geometry.banach_tarski