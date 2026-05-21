import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- For x ∈ Ioo 0 1 and t ∈ Ioo 0 1, both `deriv ↔ derivWithin (Icc 0 1)` rewrites
-- are unconditional via `derivWithin_of_mem_nhds` (Icc ∈ nhds at interior points).
-- The inner `deriv (H τ'') t = derivWithin (H τ'') (Icc 0 1) t` rewrite makes the
-- two outer functions literally equal, then the outer rewrite at x finishes.
theorem s10350
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ t ∈ Set.Ioo (0:ℝ) 1, ∀ x ∈ Set.Ioo (0:ℝ) 1,
      deriv (fun τ'' => f (H τ'' t) * deriv (H τ'') t) x =
        derivWithin (fun τ'' => f (H τ'' t) *
              derivWithin (H τ'') (Set.Icc (0:ℝ) 1) t)
          (Set.Icc (0:ℝ) 1) x  := by
  intro t ht x hx
  have hnhds_t : Set.Icc (0:ℝ) 1 ∈ nhds t := Icc_mem_nhds ht.1 ht.2
  have hnhds_x : Set.Icc (0:ℝ) 1 ∈ nhds x := Icc_mem_nhds hx.1 hx.2
  have heq : (fun τ'' => f (H τ'' t) * deriv (H τ'') t) =
      (fun τ'' => f (H τ'' t) * derivWithin (H τ'') (Set.Icc (0:ℝ) 1) t) := by
    funext τ''
    rw [derivWithin_of_mem_nhds hnhds_t]
  rw [heq]
  exact (derivWithin_of_mem_nhds hnhds_x).symm

end Problems.residue_thm
