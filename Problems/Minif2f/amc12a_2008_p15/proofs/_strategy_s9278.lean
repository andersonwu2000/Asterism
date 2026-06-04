import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs
import Problems.Minif2f.amc12a_2008_p15.proofs.L_combine_mod_pow_abs
import Problems.Minif2f.amc12a_2008_p15.proofs.L_k_ge_four
import Problems.Minif2f.amc12a_2008_p15.proofs.L_k_mod_four
import Problems.Minif2f.amc12a_2008_p15.proofs.L_k_mod_ten

namespace Problems.Minif2f.amc12a_2008_p15

-- Decompose `(k^2 + 2^k) % 10 = 6` for `k = 2008^2 + 2^2008` into 3 modular/size
-- facts about k (mod 10, mod 4, lower bound) plus an abstract arithmetic combinator
-- on any natural m. `native_decide`/`decide` are dead — `2^2008` blows recursion
-- depth (see lessons). The combinator drops the `k = 2008^2 + 2^2008` binder
-- intentionally: it is a truly abstract helper, making it strictly simpler than
-- the parent goal and reusable by other strategies.
theorem s9278 : ∀ (k : ℕ) (h₀ : k = 2008 ^ 2 + 2 ^ 2008), (k ^ 2 + 2 ^ k) % 10 = 6  := by
  intro k h₀
  have h_k_mod_10 := k_mod_ten k h₀
  have h_k_mod_4 := k_mod_four k h₀
  have h_k_ge_4 := k_ge_four k h₀
  exact combine_mod_pow_abs k h_k_mod_10 h_k_mod_4 h_k_ge_4

end Problems.Minif2f.amc12a_2008_p15
