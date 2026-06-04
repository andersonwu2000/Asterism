import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs
import Problems.Minif2f.aime_1987_p8.proofs.L_mem_112
import Problems.Minif2f.aime_1987_p8.proofs.L_ub_112

namespace Problems.Minif2f.aime_1987_p8

-- Split `IsGreatest S 112` into (a) membership `112 ∈ S` and (b) upper bound on S.
-- Combinator: `⟨h_mem, h_ub⟩` matches `IsGreatest = · ∈ S ∧ · ∈ upperBounds S`.
theorem s536 : IsGreatest { n : ℕ | 0 < n ∧ ∃! k : ℕ, (8 : ℝ) / 15 < n / (n + k) ∧ (n : ℝ) / (n + k) < 7 / 13 } 112  := by
  have h_mem := mem_112
  have h_ub := ub_112
  exact ⟨h_mem, h_ub⟩

end Problems.Minif2f.aime_1987_p8
