<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To prove a nat-subtraction polynomial identity like `n^2+2-3*n = (n-1)*(n-2)`, use `have hle : 3*n ≤ n^2+2 := by nlinarith` then `zify [show 1≤n by omega, show 2≤n by omega, hle]; ring` — `omega` rejects nonlinear terms and `nlinarith` alone won't close equalities.
- After splitting the signature across lines, the residual `∀ (S : Finset ℕ) (h₀ : ...) : S.card = 1` is still ill-formed (∀-binders take `,` not `:`); change the final `:` before `S.card = 1` to `,` or LSP errors with `unexpected token ':='; expected ','` at the `:= by sorry`.
- Auto-generated `patch.lean` puts the whole signature on one line so the inline `--` comment swallows `(h₀ : ...) : S.card = 1 := by sorry` — split signature across lines (comment on its own line) before anything else; LSP error is `unexpected token 'end'; expected ','`.
