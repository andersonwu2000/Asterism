import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
open Classical in
theorem s45_sub_4 : ∀ (P : Finset (ℝ × ℝ)) (q x y : ℝ × ℝ),
    q ∈ P → x ∈ P → y ∈ P → x ≠ y → ¬ Collinear q x y →
    (q, x, y) ∈ (P ×ˢ (P ×ˢ P)).filter
      (fun t : (ℝ × ℝ) × (ℝ × ℝ) × (ℝ × ℝ) =>
        t.2.1 ≠ t.2.2 ∧ ¬ Collinear t.1 t.2.1 t.2.2) := by
  intro P q x y hq hx hy hne hnc
  simp only [Finset.mem_filter, Finset.mem_product]
  exact ⟨⟨hq, hx, hy⟩, hne, hnc⟩

end Problems.sylvester_gallai
