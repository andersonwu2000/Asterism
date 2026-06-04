import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Zero-dimensional base case: `finrank K W ≤ 0` forces `Fin (finrank K W)` empty.
-- Take `Module.finBasis K W` (already indexed by `Fin (finrank K W)`); the ∀-claim is
-- vacuous since any `j : Fin (finrank K W)` has `j.isLt : ↑j < finrank K W ≤ 0`. Leaf.
theorem s10902
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N) (hdim : Module.finrank K W ≤ 0) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i  := by
  refine ⟨Module.finBasis K W, ?_⟩
  intro j
  exact absurd j.isLt (by omega)

end Problems.LinearAlgebra.jordan_normal_form
