import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs
import Problems.Minif2f.amc12a_2008_p15.proofs.L_combine_mod_pow
import Problems.Minif2f.amc12a_2008_p15.proofs.L_k_ge_4
import Problems.Minif2f.amc12a_2008_p15.proofs.L_k_mod_10
import Problems.Minif2f.amc12a_2008_p15.proofs.L_k_mod_4

namespace Problems.Minif2f.amc12a_2008_p15

-- Decompose `(k^2 + 2^k) % 10 = 6` for `k = 2008^2 + 2^2008` into 3 facts about k
-- (k % 10 = 0, k % 4 = 0, 4 ≤ k) plus an abstract arithmetic combinator.
-- `native_decide` is dead — `2^2008` blows recursion depth (lesson learned).
-- The combinator drops k/h₀ binders intentionally: it is a truly abstract helper
-- on any natural m satisfying the three modular/size hypotheses.
theorem s782 : ∀ (k : ℕ) (h₀ : k = 2008 ^ 2 + 2 ^ 2008), (k ^ 2 + 2 ^ k) % 10 = 6  := by
  intro k h₀
  have h1 := k_mod_10 k h₀
  have h2 := k_mod_4 k h₀
  have h3 := k_ge_4 k h₀
  exact combine_mod_pow k h1 h2 h3

end Problems.Minif2f.amc12a_2008_p15
