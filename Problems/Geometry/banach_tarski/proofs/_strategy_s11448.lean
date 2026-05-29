import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_cos_sin_combo_zero_countable
import Problems.Geometry.banach_tarski.proofs.L_x_rot_fixes_first_coord
import Problems.Geometry.banach_tarski.proofs.L_x_rot_second_coord

namespace Problems.Geometry.banach_tarski

-- x-rotation fixes coord 0 (=p 0) and sends coord 1 to cos φ·p₁ − sin φ·p₂; reduce the
-- two-clause collision set to the second-coord zero set, then case-split on p 0.
-- Sub-goals: x_rot_fixes_first_coord, x_rot_second_coord (component formulas, Builder);
-- cos_sin_combo_zero_countable (zeros of a nonzero cos/sin combination are countable, Backward).
-- p 0 ≠ 0 ⟹ clause-0 fails ⟹ ∅; p 0 = 0 ⟹ (p₁,p₂)≠0 (from p≠0) ⟹ trig zero set, .mono.
theorem s11448
    (Q : ℝ → (E ≃ᵢ E))
    (hQ : ∀ (φ : ℝ) (x : E),
      Q φ x = Matrix.toEuclideanLin
        (!![1, 0, 0; 0, Real.cos φ, -Real.sin φ; 0, Real.sin φ, Real.cos φ] :
          Matrix (Fin 3) (Fin 3) ℝ) x) :
    ∀ p : E, p ≠ 0 →
      {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0}.Countable  := by
  intro p hp
  have hc0 : ∀ (φ : ℝ), (Q φ p) 0 = p 0 := x_rot_fixes_first_coord Q hQ p
  have hc1 : ∀ (φ : ℝ), (Q φ p) 1 = Real.cos φ * p 1 - Real.sin φ * p 2 :=
    x_rot_second_coord Q hQ p
  by_cases h0 : p 0 = 0
  · have hne : p 1 ≠ 0 ∨ p 2 ≠ 0 := by
      by_contra h
      rw [not_or, not_not, not_not] at h
      apply hp
      ext i
      fin_cases i
      · exact h0
      · exact h.1
      · exact h.2
    have hsub : {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0}
        ⊆ {φ : ℝ | Real.cos φ * p 1 - Real.sin φ * p 2 = 0} := by
      intro φ hφ
      simp only [Set.mem_setOf_eq] at hφ ⊢
      rw [← hc1 φ]; exact hφ.2
    have hcount : {φ : ℝ | Real.cos φ * p 1 - Real.sin φ * p 2 = 0}.Countable :=
      cos_sin_combo_zero_countable (p 1) (p 2) hne
    exact hcount.mono hsub
  · have hempty : {φ : ℝ | (Q φ p) 0 = 0 ∧ (Q φ p) 1 = 0} = ∅ := by
      ext φ
      simp only [Set.mem_setOf_eq, Set.mem_empty_iff_false, iff_false, not_and]
      intro hcc _
      apply h0
      rw [← hc0 φ]; exact hcc
    rw [hempty]; exact Set.countable_empty

end Problems.Geometry.banach_tarski
