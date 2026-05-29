import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_sphere_fixed_action_invariant
import Problems.Geometry.banach_tarski.proofs.L_sphere_fixed_union_countable

namespace Problems.Geometry.banach_tarski

-- Take D := the union, over nontrivial words w, of the fixed points of φ w on the unit sphere:
--   D = ⋃ (w ≠ 1) {x ∈ sphere 0 1 | φ w x = x}. Combinator: `refine ⟨D, …⟩` with five branches.
-- Sub-goal `sphere_fixed_union_countable` (Builder) — D is countable: the index FreeGroup (Fin 2)
--   is countable and each fiber is finite (hfin), so the union is countable; this drops all
--   action/geometry reasoning, hence strictly simpler.
-- Sub-goal `sphere_fixed_action_invariant` (Backward) — φ w • x ∈ sphere \ D for x ∈ sphere \ D:
--   φ w fixes 0 ⇒ it preserves the sphere, and the conjugation argument (w⁻¹vw fixes x whenever
--   v fixes φ w x) keeps φ w • x out of D; isolates a single conjunct of the parent.
-- The remaining three branches are immediate from the definition and closed inline:
--   D ⊆ sphere (each member set is a sphere subset); 0 ∉ D (0 ∉ sphere 0 1); freeness off D
--   (a fixed point on the sphere would itself lie in D, contradicting x ∉ D).
theorem s11471
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (hfin : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}.Finite) :
    ∃ D : Set E, D.Countable ∧ D ⊆ Metric.sphere (0 : E) 1 ∧ (0 : E) ∉ D ∧
      (∀ (w : FreeGroup (Fin 2)) (x : E),
          x ∈ Metric.sphere (0 : E) 1 \ D → φ w • x ∈ Metric.sphere (0 : E) 1 \ D) ∧
      (∀ (w : FreeGroup (Fin 2)), w ≠ 1 →
          ∀ x ∈ Metric.sphere (0 : E) 1 \ D, φ w • x ≠ x)  := by
  classical
  refine ⟨⋃ (w : FreeGroup (Fin 2)) (_ : w ≠ 1),
      {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}, ?_, ?_, ?_, ?_, ?_⟩

  · -- countable
    exact sphere_fixed_union_countable φ hfin
  · -- D ⊆ sphere
    intro x hx
    simp only [Set.mem_iUnion, Set.mem_setOf_eq] at hx
    obtain ⟨w, _, hx, _⟩ := hx
    exact hx
  · -- 0 ∉ D
    intro h0
    simp only [Set.mem_iUnion, Set.mem_setOf_eq] at h0
    obtain ⟨w, _, h0, _⟩ := h0
    rw [Metric.mem_sphere, dist_self] at h0
    exact zero_ne_one h0
  · -- invariance
    exact sphere_fixed_action_invariant φ hfix0
  · -- free off D
    intro w hw x hx hfx
    apply hx.2
    simp only [Set.mem_iUnion, Set.mem_setOf_eq]
    exact ⟨w, hw, hx.1, hfx⟩



end Problems.Geometry.banach_tarski
