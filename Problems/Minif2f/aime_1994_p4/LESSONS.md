<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For non-negativity goals `(0 : ℤ) ≤ ⌊logb 2 k⌋` (k : ℕ, 1 ≤ k), use `Int.floor_nonneg.mpr` then `Real.logb_nonneg` (· `norm_num` for base ≥ 1, · `exact_mod_cast hk` for arg ≥ 1) — no need for `floor_logb_natCast`/`Int.log_natCast`/`decide`.
- `Real.floor_logb_natCast` requires BOTH base and argument to be syntactic `Nat.cast`s; for `Real.logb 2 ↑k` first rewrite `(2 : ℝ) = ((2 : ℕ) : ℝ)` via `norm_num`, otherwise the `rw` fails with "Did not find an occurrence of the pattern ⌊Real.logb ↑?b ↑k⌋".
- For goals with `Int.floor (Real.logb 2 (k : ℕ))`, the chain `Real.floor_logb_natCast (Nat.cast_nonneg k)` then `Int.log_natCast` reduces each term to computable `Nat.log`; close the resulting finset-sum inequality with `set_option maxRecDepth 2000 in decide` — never `native_decide`, which adds rogue axioms rejected by the framework's axiom check.
