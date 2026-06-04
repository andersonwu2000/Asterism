# miniF2F wider pilot v3 — signature-normalize fix validated

HEAD `2b84b56` (adapters/minif2f: normalize signature to ∀-form)
Daemon pid **110404**, started 2026-05-12 00:51:58
Background task: `blpwnug1d`
Scope: `Minif2f.%`, pool=15, entry=Backward × 20

## The bug that v2 hit

miniF2F file format:
```
theorem foo (a b c d : ℂ) : <type> := by sorry
```

Adapter captured raw signature `(a b c d : ℂ) : <type>`. cmd_init wrapped
as `theorem main : {statement} := by sorry`, producing:

```
theorem main : (a b c d : ℂ) : <type> := by sorry
              ↑               ↑
            outer wrapper    miniF2F's separator → DOUBLE COLON
```

That Root.lean is syntactically invalid. Backward agent reading it (via
F52 signature lock requiring binder match) copied the same broken
pattern into `_strategy_s<id>.lean`. lake_build_error every retry,
Phase 7 helper exhausted, no patch ever closed.

Pilot v2 result: 15 spawns dispatched, 15 → exhausted, 0 proved.

## Fix (commit `2b84b56`)

`_normalize_signature` walks the signature with paren-depth tracking,
finds the FIRST top-level `:` (the binder/conclusion separator),
rewrites as `∀ <binders>, <conclusion>`:

| Input | Output |
|---|---|
| `: P` (nullary) | `P` |
| `(x : ℝ) : x = x` | `∀ (x : ℝ), x = x` |
| `(a b : ℕ) (h : a > 0) : a + b > 0` | `∀ (a b : ℕ) (h : a > 0), a + b > 0` |
| `{X : Type*} [Inst X] (x : X) : True` | `∀ {X : Type*} [Inst X] (x : X), True` |

After fix, cmd_init produces valid Lean:
```
theorem main : ∀ (a b c d : ℂ), <type> := by sorry
```

Confirmed on disk after re-import: `Problems/Minif2f/<each>/Root.lean`
parses cleanly.

## Hypothesis

With the bug fixed, Backward agents should:
1. See valid Root.lean
2. Produce valid strategy patches matching parent binders
3. Either close via leaf-bypass (trivial problems) or decompose into
   sub-goals (harder problems)

Expected success rate based on v1 (pool=3 hotfix, entry=Builder):
17/20 = 85%. v3 with entry=Backward should be comparable; Backward
adds a level of indirection for trivial problems but doesn't break
the cascade.

## Pending: cadence findings + final results
