<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To prove `(⌊x⌋ : ℝ) < x` when `x = (k+1)·φ` is irrational, apply `lt_of_le_of_ne (Int.floor_le _)`, derive `(k+1)·√5 = integer` via `linear_combination 2 * h`, then contradict `Nat.Prime.irrational_sqrt (by norm_num : Nat.Prime 5)` by constructing a ℚ witness with `refine ⟨(... : ℤ : ℚ) / ((k:ℤ)+1 : ℚ), ?_⟩` + `push_cast; rw [div_eq_iff ...]; linarith [mul_comm (Real.sqrt 5) _]`.
- For inequalities mixing `(⌊x⌋ : ℝ) * φ` with an irrational `φ`, bare `nlinarith` with `Real.mul_self_sqrt` hints won't close it; first multiply `Int.sub_one_lt_floor _ : x - 1 < ⌊x⌋` by `(φ - 1) > 0` via `mul_le_mul_of_nonneg_right` to introduce the `⌊x⌋·(φ-1)` term, then `nlinarith` succeeds using `√5·√5 = 5` (φ²=φ+1) and `√5 ≤ 3` (φ≤2).
- For the witness `f n = (⌊((n:ℝ)+1)·φ⌋).toNat - 1`, first prove `1 ≤ ⌊((n:ℝ)+1)·φ⌋`, then bridge ℕ↔ℤ via `Int.toNat_of_nonneg` + `Nat.cast_sub` (giving `(((F.toNat - 1 : ℕ) : ℝ) + 1) = (F : ℝ)`) and `Int.toNat_add` + `Int.toNat_natCast` (giving `(F + n).toNat = F.toNat + n`); `omega` closes the final ℕ-subtraction step.
- For floor goals involving `Real.sqrt k`, bound it with `nlinarith [Real.sq_sqrt (by norm_num : (0:ℝ) ≤ k), Real.sqrt_nonneg k]`, then close `⌊expr⌋ = n` via `rw [Int.floor_eq_iff]` (no extra argument) + `push_cast` + `linarith`.
- patch.lean namespace must be `Problems.Minif2f.imo_1993_p5` (dots, matching directory hierarchy); LSP `validate_file` silently accepts underscore variants but the lake axiom probe uses the namespace declared in the actual `L_*.lean` file, causing `constant not found`.
