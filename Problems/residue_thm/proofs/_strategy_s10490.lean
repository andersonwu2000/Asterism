import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_ball_cover_partition_of_compact_path
import Problems.residue_thm.proofs.L_c2_loop_through_ball_cover_partition

namespace Problems.residue_thm

-- Decompose: (A) compactness of γ([0,1]) + openness of U → finite partition + ball cover for γ,
-- (B) given that partition+cover for γ, build a C² loop η matching γ at subdivision points and
-- lying in the same balls per piece. Combine the two witnesses to satisfy the parent's conjunction.
theorem s10490
    {U : Set ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    ∃ (η : ℝ → ℂ) (n : ℕ) (t : ℕ → ℝ) (centers : ℕ → ℂ) (radii : ℕ → ℝ),
      ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
      Set.MapsTo η (Set.Icc (0:ℝ) 1) U ∧
      η 0 = η 1 ∧
      η 0 = γ 0 ∧
      t 0 = 0 ∧ t n = 1 ∧
      (∀ i, i < n → t i ≤ t (i+1)) ∧
      (∀ i, i < n → 0 < radii i) ∧
      (∀ i, i < n → Metric.ball (centers i) (radii i) ⊆ U) ∧
      (∀ i, i < n → Set.MapsTo γ (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) ∧
      (∀ i, i < n → Set.MapsTo η (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) ∧
      (∀ i, i ≤ n → η (t i) = γ (t i))  := by
  obtain ⟨n, t, centers, radii, ht0, htn, htmono, hrpos, hballsubU, hgammacov⟩ :=
    ball_cover_partition_of_compact_path hU hγ hmaps
  obtain ⟨η, hηC2, hηmaps, hηclosed, hη0, hηcov, hηeq⟩ :=
    c2_loop_through_ball_cover_partition hU hγ hmaps hclosed n t centers radii
      ht0 htn htmono hrpos hballsubU hgammacov
  exact ⟨η, n, t, centers, radii, hηC2, hηmaps, hηclosed, hη0, ht0, htn,
    htmono, hrpos, hballsubU, hgammacov, hηcov, hηeq⟩



end Problems.residue_thm
