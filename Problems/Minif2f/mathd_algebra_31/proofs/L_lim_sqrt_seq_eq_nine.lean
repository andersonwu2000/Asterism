import Mathlib
import Problems.Minif2f.mathd_algebra_31.Defs

namespace Problems.Minif2f.mathd_algebra_31

open scoped Topology

set_option linter.style.longLine false in
-- lim_sqrt_seq_eq_nine: rewrite sequence via h₀ to u(·+1), then compose h₁ with atTop shift
theorem lim_sqrt_seq_eq_nine (x : NNReal) (u : ℕ → NNReal) (h₀ : ∀ n, u (n + 1) = NNReal.sqrt (x + u n)) (h₁ : Filter.Tendsto u Filter.atTop (𝓝 9)) : Filter.Tendsto (fun n => NNReal.sqrt (x + u n)) Filter.atTop (𝓝 9) := by
  have heq : ∀ n, NNReal.sqrt (x + u n) = u (n + 1) := fun n => (h₀ n).symm
  simp_rw [heq]
  exact h₁.comp (Filter.tendsto_atTop_atTop_of_monotone
    (fun a b h => Nat.add_le_add_right h 1)
    (fun b => ⟨b, Nat.le_add_right b 1⟩))

end Problems.Minif2f.mathd_algebra_31
