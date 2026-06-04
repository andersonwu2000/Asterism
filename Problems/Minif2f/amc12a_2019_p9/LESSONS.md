<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- When `field_simp` with ℕ-cast ℚ non-zero hints leaves a residual `X / Y = 1` goal that `ring` won't close, add `have hd : Y ≠ 0 := by push_cast; linarith [Nat.zero_le k]` then close with `rw [div_eq_iff hd]; push_cast; ring`.
- For closing `↑(q : ℚ).den + q.num = N` on a literal `q` like `3/8075`, use `native_decide`; plain `decide` gets stuck failing to reduce `Rat.num`/`Rat.den` in the kernel.
