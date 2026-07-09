import Mathlib.AlgebraicTopology.SimplexCategory.Basic
import Mathlib.SetTheory.Cardinal.Free
import Library.Geometry.BanachTarski.Defs

/-!
# Fixed-point set and free action off a countable exceptional set

Let `φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)` be an isometric action of the free group on two
generators on a normed space `E`. This file shows that if `φ` fixes the origin and has finite
fixed-point fibers on the unit sphere, then there exists a countable exceptional set `D` contained
in the sphere such that `φ` acts freely on the complement `sphere \ D`.

## Main statements

* `sphere_fixed_action_invariant` — the complement of the union of fixed-point fibers is invariant
  under the action of `φ`.
* `sphere_fixed_union_countable` — the union of fixed-point fibers over all nontrivial group
  elements is countable.
* `fixed_free_action_off_countable` — there exists a countable set `D ⊆ sphere` such that `φ`
  is free on `sphere \ D`.
-/

open Library.Geometry.BanachTarski.Defs

namespace Library.Geometry.BanachTarski.FixedFreeAction

/-- The complement `Metric.sphere 0 1 \ D` of the union of fixed-point fibers
$D = \bigcup_{w \neq 1} \{x \in S \mid \varphi(w)(x) = x\}$ is invariant under the action of
`φ`. Assuming each `φ w` fixes the origin, it preserves the unit sphere. The key conjugation
argument shows: if `v` fixes `φ w x`, then `w⁻¹ * v * w` fixes `x`, so `φ w x ∈ D` would
force `x ∈ D`. -/
theorem sphere_fixed_action_invariant
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0) :
    ∀ (w : FreeGroup (Fin 2)) (x : E),
        x ∈ Metric.sphere (0 : E) 1 \
            (⋃ (v : FreeGroup (Fin 2)) (_ : v ≠ 1),
                {y ∈ Metric.sphere (0 : E) 1 | φ v y = y}) →
        φ w • x ∈ Metric.sphere (0 : E) 1 \
            (⋃ (v : FreeGroup (Fin 2)) (_ : v ≠ 1),
                {y ∈ Metric.sphere (0 : E) 1 | φ v y = y}) := by
  intro w x hx
  obtain ⟨hx_sph, hx_notD⟩ := hx
  refine ⟨?_, ?_⟩
  · simp only [Metric.mem_sphere] at hx_sph ⊢
    change dist (φ w x) 0 = 1
    rw [← hfix0 w, (φ w).dist_eq]
    exact hx_sph
  · intro hmem
    apply hx_notD
    simp only [Set.mem_iUnion, Set.mem_setOf_eq] at hmem ⊢
    obtain ⟨v, hv, _, hv_fix⟩ := hmem
    change (φ v) ((φ w) x) = (φ w) x at hv_fix
    refine ⟨w⁻¹ * v * w, ?_, hx_sph, ?_⟩
    · intro hone
      apply hv
      have hvc : v = w * (w⁻¹ * v * w) * w⁻¹ := by group
      rw [hvc, hone]; group
    · show φ (w⁻¹ * v * w) x = x
      rw [map_mul, map_mul]
      change (φ w⁻¹) ((φ v) ((φ w) x)) = x
      rw [hv_fix, map_inv]
      change (φ w).symm ((φ w) x) = x
      exact (φ w).symm_apply_apply x

/-- The union of fixed-point fibers $\{x \in S \mid \varphi(w)(x) = x\}$ over all nontrivial
`w : FreeGroup (Fin 2)` is countable. Since `FreeGroup (Fin 2)` is countable and each fiber is
assumed finite by `hfin`, the countable union of finite sets is countable. -/
theorem sphere_fixed_union_countable
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (hfin : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}.Finite) :
    (⋃ (w : FreeGroup (Fin 2)) (_ : w ≠ 1),
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}).Countable := by
  apply Set.countable_iUnion
  intro w
  by_cases hw : w = 1
  · simp [hw]
  · exact (hfin w hw).countable.mono (Set.iUnion_subset fun _ => subset_refl _)

/-- **Free action off a countable exceptional set**: given an isometric action
`φ : FreeGroup (Fin 2) →* (E ≃ᵢ E)` that fixes the origin and has finite fixed-point fibers on
the unit sphere, there exists a countable set `D ⊆ Metric.sphere 0 1` with `0 ∉ D` such that
`φ` preserves `sphere \ D` and acts freely on it.

The exceptional set is $D = \bigcup_{w \neq 1} \{x \in S \mid \varphi(w)(x) = x\}$.
Countability follows from `sphere_fixed_union_countable`; invariance from
`sphere_fixed_action_invariant`. -/
theorem fixed_free_action_off_countable
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0)
    (hfin : ∀ w : FreeGroup (Fin 2), w ≠ 1 →
        {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}.Finite) :
    ∃ D : Set E, D.Countable ∧ D ⊆ Metric.sphere (0 : E) 1 ∧ (0 : E) ∉ D ∧
      (∀ (w : FreeGroup (Fin 2)) (x : E),
          x ∈ Metric.sphere (0 : E) 1 \ D → φ w • x ∈ Metric.sphere (0 : E) 1 \ D) ∧
      (∀ (w : FreeGroup (Fin 2)), w ≠ 1 →
          ∀ x ∈ Metric.sphere (0 : E) 1 \ D, φ w • x ≠ x) := by
  classical
  refine ⟨⋃ (w : FreeGroup (Fin 2)) (_ : w ≠ 1),
      {x ∈ Metric.sphere (0 : E) 1 | φ w x = x}, ?_, ?_, ?_, ?_, ?_⟩
  · exact sphere_fixed_union_countable φ hfin
  · intro x hx
    simp only [Set.mem_iUnion, Set.mem_setOf_eq] at hx
    obtain ⟨w, _, hx, _⟩ := hx
    exact hx
  · intro h0
    simp only [Set.mem_iUnion, Set.mem_setOf_eq] at h0
    obtain ⟨w, _, h0, _⟩ := h0
    rw [Metric.mem_sphere, dist_self] at h0
    exact zero_ne_one h0
  · exact sphere_fixed_action_invariant φ hfix0
  · intro w hw x hx hfx
    apply hx.2
    simp only [Set.mem_iUnion, Set.mem_setOf_eq]
    exact ⟨w, hw, hx.1, hfx⟩

end Library.Geometry.BanachTarski.FixedFreeAction
