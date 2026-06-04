import Mathlib
import Problems.Minif2f.imo_1993_p5.proofs.L_wythoff_floor_pos
import Problems.Minif2f.imo_1993_p5.proofs.L_wythoff_floor_step

namespace Problems.Minif2f.imo_1993_p5

-- Split the Beatty-type identity f(f n) = f n + n for f n = ⌊(n+1)φ⌋.toNat - 1.
-- Sub-goals abstract away ℕ/ℤ/ℝ cast bookkeeping:
--   wythoff_floor_pos  : ⌊(n+1)φ⌋ ≥ 1 (so (·).toNat - 1 is non-truncating)
--   wythoff_floor_step : ⌊⌊(n+1)φ⌋ · φ⌋ = ⌊(n+1)φ⌋ + n  (core golden-ratio identity)
-- Combinator: setF := ⌊(n+1)φ⌋; bridge ((F.toNat - 1 : ℕ) : ℝ) + 1 = (F : ℝ);
-- apply wythoff_floor_step at n; unwind toNat via Int.toNat_add + Int.toNat_natCast.
theorem s9949 :
    ∀ n : ℕ,
      (fun m : ℕ => (⌊((m : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋).toNat - 1)
          ((fun m : ℕ => (⌊((m : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋).toNat - 1) n)
        = (fun m : ℕ => (⌊((m : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋).toNat - 1) n + n := by
  have h_pos : ∀ k : ℕ, (1 : ℤ) ≤ ⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ := wythoff_floor_pos
  have h_inner : ∀ k : ℕ,
      ⌊(⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ : ℝ) * ((1 + Real.sqrt 5) / 2)⌋
        = ⌊((k : ℝ) + 1) * ((1 + Real.sqrt 5) / 2)⌋ + (k : ℤ) := wythoff_floor_step

  intro n
  simp only []
  set φ : ℝ := (1 + Real.sqrt 5) / 2 with hφ
  set F : ℤ := ⌊((n : ℝ) + 1) * φ⌋ with hF_def
  have hF_pos : (1 : ℤ) ≤ F := h_pos n
  have hF_nn : (0 : ℤ) ≤ F := by linarith
  have hF_toNat_eq : (F.toNat : ℤ) = F := Int.toNat_of_nonneg hF_nn
  have hF_toNat_pos : 1 ≤ F.toNat := by
    have : (1 : ℤ) ≤ (F.toNat : ℤ) := hF_toNat_eq ▸ hF_pos
    exact_mod_cast this
  have hcast : (((F.toNat - 1 : ℕ) : ℝ) + 1) = (F : ℝ) := by
    have h1 : ((F.toNat - 1 : ℕ) : ℝ) = (F.toNat : ℝ) - 1 := by
      rw [Nat.cast_sub hF_toNat_pos]; push_cast; ring
    have h2 : ((F.toNat : ℝ)) = (F : ℝ) := by
      have := hF_toNat_eq
      exact_mod_cast this
    linarith
  have h_inner_n := h_inner n
  have hgoal_lhs : ⌊(((F.toNat - 1 : ℕ) : ℝ) + 1) * φ⌋ = F + n := by
    rw [hcast]; exact h_inner_n
  have hFn_nn : (0 : ℤ) ≤ F + n := by positivity
  have hFn_toNat : (F + n).toNat = F.toNat + n := by
    have := Int.toNat_add hF_nn (Int.natCast_nonneg n)
    rw [this, Int.toNat_natCast]
  change (⌊(((F.toNat - 1 : ℕ) : ℝ) + 1) * φ⌋).toNat - 1 = (F.toNat - 1) + n

  rw [hgoal_lhs, hFn_toNat]
  omega

end Problems.Minif2f.imo_1993_p5
