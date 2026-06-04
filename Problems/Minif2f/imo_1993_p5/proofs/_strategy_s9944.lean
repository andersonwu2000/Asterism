import Mathlib
import Problems.Minif2f.imo_1993_p5.proofs.L_wythoff_func
import Problems.Minif2f.imo_1993_p5.proofs.L_wythoff_mono
import Problems.Minif2f.imo_1993_p5.proofs.L_wythoff_one

namespace Problems.Minif2f.imo_1993_p5

-- commit to the upper-Wythoff witness  f(n) = ⌊(n+1)φ⌋ - 1  with φ = (1+√5)/2
-- and split verification into three claims about that explicit f:
--   wythoff_one : f 1 = 2                       (numerical)
--   wythoff_func: ∀ n, f (f n) = f n + n        (Beatty-type identity for φ)
--   wythoff_mono: ∀ n, f n < f (n + 1)          (strict monotonicity of (n+1)φ floor)
-- combinator re-shuffles `∀ n, A n ∧ ∀ n, B` into the parent's nested form.
theorem s9944 : ∃ f : ℕ → ℕ, f 1 = 2 ∧ ∀ n, f (f n) = f n + n ∧ ∀ n, f n < f (n + 1)  := by
  classical
  set f : ℕ → ℕ :=
    fun n => (⌊((n : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋).toNat - 1 with hf_def
  have h_one : f 1 = 2 := wythoff_one
  have h_func : ∀ n, f (f n) = f n + n := wythoff_func
  have h_mono : ∀ n, f n < f (n + 1) := wythoff_mono
  exact ⟨f, h_one, fun n => ⟨h_func n, h_mono⟩⟩

end Problems.Minif2f.imo_1993_p5
