import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct telescoping proof (leaf): the prefix sum of the gaps recovers `b t`.
-- Extend `b` to `f : ℕ → ℕ`, `f i = if i < p then b ⟨i,_⟩ else n` (monotone via `hmono`/`hlt`).
-- For every `j < t < p` the `dif` always takes its true branch (`↑j+1 ≤ t < p`), so each
-- gap term equals `f (↑j+1) - f ↑j`; `Fin.sum_univ_eq_sum_range` + `Finset.sum_range_tsub`
-- telescope it to `f t - f 0 = b t - 0 = b t` (`f t = b t` since `t < p`, `f 0 = b ⟨0,_⟩ = 0`
-- by `hzero`).
theorem s10936 {n p : ℕ} (b : Fin p → ℕ)
    (hmono : StrictMono b) (hlt : ∀ t : Fin p, b t < n)
    (hzero : ∀ t : Fin p, (t : ℕ) = 0 → b t = 0)
    (hp : 0 < n → 0 < p) :
    ∀ t : Fin p,
      (∑ j : Fin ↑t,
        (fun (s : Fin p) =>
          if h : (s : ℕ) + 1 < p then b ⟨(s : ℕ) + 1, h⟩ - b s else n - b s)
            (Fin.castLE t.isLt.le j)) = b t  := by
  intro t
  set f : ℕ → ℕ := fun i => if h : i < p then b ⟨i, h⟩ else n with hf