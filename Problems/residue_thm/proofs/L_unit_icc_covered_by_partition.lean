import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- unit_icc_covered_by_partition: every τ ∈ Icc 0 1 lies in some Icc (t i) (t (i+1))
-- via induction on n, splitting on σ ≤ s 1 at each step.
theorem unit_icc_covered_by_partition
    {n : ℕ} (t : ℕ → ℝ)
    (ht0 : t 0 = 0) (htn : t n = 1)
    (htmono : ∀ i, i < n → t i ≤ t (i + 1))
    {τ : ℝ} (hτ : τ ∈ Set.Icc (0 : ℝ) 1) :
    ∃ i, i < n ∧ τ ∈ Set.Icc (t i) (t (i + 1)) := by
  have key : ∀ m (s : ℕ → ℝ), (∀ i, i < m + 1 → s i ≤ s (i + 1)) →
      ∀ σ, σ ∈ Set.Icc (s 0) (s (m + 1)) →
      ∃ i, i < m + 1 ∧ σ ∈ Set.Icc (s i) (s (i + 1)) := by
    intro m
    induction m with
    | zero =>
      intro s _ σ hσ
      exact ⟨0, Nat.zero_lt_one, hσ⟩
    | succ m ih =>
      intro s hmono σ hσ
      by_cases h : σ ≤ s 1
      · exact ⟨0, Nat.zero_lt_succ _, ⟨hσ.1, h⟩⟩
      · push Not at h
        have hmono' : ∀ i, i < m + 1 → (fun i => s (i + 1)) i ≤ (fun i => s (i + 1)) (i + 1) :=
          fun i hi => hmono (i + 1) (by omega)
        have hσ' : σ ∈ Set.Icc ((fun i => s (i + 1)) 0) ((fun i => s (i + 1)) (m + 1)) :=
          ⟨le_of_lt h, hσ.2⟩
        obtain ⟨j, hj, hjσ⟩ := ih (fun i => s (i + 1)) hmono' σ hσ'
        exact ⟨j + 1, by omega, hjσ⟩
  obtain ⟨m, rfl⟩ : ∃ m, n = m + 1 := by
    cases n with
    | zero => simp [ht0] at htn
    | succ m => exact ⟨m, rfl⟩
  exact key m t (fun i hi => htmono i hi) τ (by constructor <;> [rw [ht0]; rw [htn]] <;>
    [exact hτ.1; exact hτ.2])

end Problems.residue_thm
