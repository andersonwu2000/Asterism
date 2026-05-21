import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct application of Mathlib's Schwarz symmetry: `ContDiffWithinAt.isSymmSndFDerivWithinAt`.
-- The point `(τ, t)` lies in `closure (interior (Icc×Icc)) = closure (Ioo×Ioo) = Icc×Icc`,
-- and `hH` supplies `ContDiffWithinAt ℝ 2` there; `UniqueDiffOn` on the product follows
-- from `uniqueDiffOn_Icc_zero_one.prod`. Conclude via `IsSymmSndFDerivWithinAt.eq`.
theorem s10395
    {H : ℝ → ℝ → ℂ}
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1)) :
    ∀ τ ∈ Set.Ico (0:ℝ) 1, ∀ t ∈ Set.Ioo (0:ℝ) 1,
      (fderivWithin ℝ (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t)) (0, 1) (1, 0) =
        (fderivWithin ℝ (fderivWithin ℝ (fun p : ℝ × ℝ => H p.1 p.2)
              (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t)) (1, 0) (0, 1)  := by
  intro τ hτ t ht
  have hτ_mem : τ ∈ Set.Icc (0:ℝ) 1 := Set.Ico_subset_Icc_self hτ
  have ht_mem : t ∈ Set.Icc (0:ℝ) 1 := Set.Ioo_subset_Icc_self ht
  have hmem : (τ, t) ∈ Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1 := Set.mk_mem_prod hτ_mem ht_mem
  have huniq : UniqueDiffOn ℝ (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    uniqueDiffOn_Icc_zero_one.prod uniqueDiffOn_Icc_zero_one
  have hclos : (τ, t) ∈ closure (interior (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1)) := by
    rw [interior_prod_eq, interior_Icc, closure_prod_eq, closure_Ioo (by norm_num : (0:ℝ) ≠ 1)]
    exact hmem
  have hsym : IsSymmSndFDerivWithinAt ℝ (fun p : ℝ × ℝ => H p.1 p.2)
      (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) (τ, t) :=
    (hH.contDiffWithinAt hmem).isSymmSndFDerivWithinAt (by simp) huniq hclos hmem
  exact hsym (0, 1) (1, 0)

end Problems.residue_thm
