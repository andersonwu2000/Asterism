import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- φ w preserves sphere\D: on-sphere via the isometry φ w fixing 0; off-D via conjugation.
-- If φ v fixed φ w • x for some v ≠ 1, then w⁻¹vw (≠ 1) fixes x, so x ∈ D — contradiction.
-- Direct sorry-free proof (no sub-goals): `map_mul`/`map_inv`/`symm_apply_apply` + `group`.
theorem s11477
    (φ : FreeGroup (Fin 2) →* (E ≃ᵢ E))
    (hfix0 : ∀ w : FreeGroup (Fin 2), φ w 0 = 0) :
    ∀ (w : FreeGroup (Fin 2)) (x : E),
        x ∈ Metric.sphere (0 : E) 1 \
            (⋃ (v : FreeGroup (Fin 2)) (_ : v ≠ 1),
                {y ∈ Metric.sphere (0 : E) 1 | φ v y = y}) →
        φ w • x ∈ Metric.sphere (0 : E) 1 \
            (⋃ (v : FreeGroup (Fin 2)) (_ : v ≠ 1),
                {y ∈ Metric.sphere (0 : E) 1 | φ v y = y})  := by
  intro w x hx
  obtain ⟨hx_sph, hx_notD⟩ := hx
  refine ⟨?_, ?_⟩
  · -- φ w • x stays on the sphere: φ w is an isometry fixing 0
    simp only [Metric.mem_sphere] at hx_sph ⊢
    change dist (φ w x) 0 = 1
    rw [← hfix0 w, (φ w).dist_eq]
    exact hx_sph
  · -- φ w • x stays out of D, by the conjugation argument
    intro hmem
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

end Problems.Geometry.banach_tarski

