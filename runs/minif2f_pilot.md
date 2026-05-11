# miniF2F pilot — 5 mathd_algebra problems

HEAD `2bcad9f` (Benchmarks/ separation + adapter)
Daemon pid **103560**, started 2026-05-11 19:44:48
Background task: `bg7mhau3d`
Backward model: claude-opus-4-7 / Builder: claude-sonnet-4-6 (current Asterism.yaml)

## Purpose

Validate end-to-end:
- miniF2F adapter generates valid Asterism Problem dirs
- Framework dispatches Builder on imported problems
- LSP gateway elaborates `import Mathlib` + `set_option maxHeartbeats 0`
- Get first pilot success/failure numbers for demo

## Imported problems

| Slug | Original miniF2F name |
|---|---|
| minif2f_mathd_algebra_10 | mathd_algebra_10 |
| minif2f_mathd_algebra_101 | mathd_algebra_101 |
| minif2f_mathd_algebra_104 | mathd_algebra_104 |
| minif2f_mathd_algebra_109 | mathd_algebra_109 |
| minif2f_mathd_algebra_11 | mathd_algebra_11 |

All entry_kind=Builder (miniF2F problems are leaf-shaped — single-shot
proof attempts rather than multi-level decomposition).

## Pending: cadence findings + final results
