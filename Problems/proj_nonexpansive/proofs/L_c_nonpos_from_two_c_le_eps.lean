-- c_nonpos_from_two_c_le_eps: Closes by `by_contra` + specializing `hf` at `ε = c` when `c > 0`, giving `2 * c ≤ c`, then `linarith` derives the contradiction.
--
-- ## Strategy
--
-- Uses the hypothesis `hf : ∀ ε : ℝ, 0 < ε → 2 * c ≤ ε` directly: if `c > 0`, specialize at `ε = c` to obtain `2 * c ≤ c`, which `linarith` immediately contradicts. No Mathlib lemma beyond `push_neg` and `linarith` is needed.
import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- entry_kind: Builder
theorem c_nonpos_from_two_c_le_eps (c M : ℝ) (hM : 0 ≤ M)
    (h : ∀ t : ℝ, 0 < t → t ≤ 1 → 2 * c ≤ t * M)
    (hf : ∀ ε : ℝ, 0 < ε → 2 * c ≤ ε) :
    c ≤ 0 := by
  by_contra h_neg
  push_neg at h_neg
  have := hf c h_neg
  linarith

end Problems.proj_nonexpansive
