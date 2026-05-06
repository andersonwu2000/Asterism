import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- inner_diff_combine: pure inner-product identity: ⟨x−y,c−d⟩ − ‖c−d‖² = ⟨c−x,d−c⟩ + ⟨d−y,c−d⟩
-- entry_kind: Builder
theorem inner_diff_combine {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    (x y c d : X) :
    @inner ℝ _ _ (x - y) (c - d) - ‖c - d‖ ^ 2 =
      @inner ℝ _ _ (c - x) (d - c) + @inner ℝ _ _ (d - y) (c - d) := by sorry

end Problems.proj_nonexpansive
