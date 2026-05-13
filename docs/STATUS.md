# Asterism — Current Status

更新於 **2026-05-13**、HEAD `c0cc7cf`、781 unit tests green / 1 skipped。

## TL;DR

miniF2F-Valid 244-題 pilot 完成、結果 + 反思 + 修復記錄全在
**[`docs/internal_report_minif2f_pilot.md`](internal_report_minif2f_pilot.md)**。

關鍵 takeaway：
- **235/244 proved（96.3% raw、嚴格 axiom audit）+ 9 disproved（kernel-verified errata）= 244/244 全 classified**
- 同寬鬆標準下 ≈ 100%（業界數字若沒揭露怎處理 false statement、不可直比）
- 這次 run 中段發現 framework correctness gap（workspace-AND gate bug）、已修
- audit 跑完確認 0 sorryAx leak、3 個 native_decide（接受、業界標準做法）

## 最近 commit

| Commit | 內容 |
|---|---|
| `c0cc7cf` | docs(internal-report): 修正 industry comparison 數字 |
| `ba786e9` | docs: internal report for miniF2F-Valid 244 pilot |
| `6828076` | miniF2F: propagate open clauses to all proof files in 3 patched problems |
| `6a00de2` | errata: mention full-Valid-split coverage as supporting evidence |
| `b65029f` | errata: retract fabricated 'facebookresearch PR #36' claim |
| `986ea3d` | errata: draft single-issue upstream report for 9 miniF2F-valid bugs |
| `6906399` | cli: replay Defs.lean opens into Root.lean stub on init/reset |
| `147bec5` | dispatcher: fix workspace-AND gate, restore per-problem library promote |

## 對外送出材料

- `docs/errata/minif2f/upstream_issue.md` — ready-to-post GitHub issue body
  for `yangky11/miniF2F-lean4`（9 個 errata）
- `docs/proposal/{proposal,comparison,demo_script,sg_cascade}.md` — 給教授的
  pitch 材料
- `docs/internal_report_minif2f_pilot.md` — 內部完整版（教授版從此提煉）

## Framework follow-ups（pending tasks）

詳見 internal report §9。優先級高的：
- **#117** framework propagate Defs.lean opens 給 agent-authored files
  （這次 run 發現的、cmd_init `6906399` fix 的延續）
- #106 Phase 2 Theorist Pipeline 設計 doc
  （imo_1993_p5 + amc12a_2009_p25 已 prove "minimal hint → IMO-tier proof" works）

## 其他歷史 SG / PN / IZ 等 single-problem runs

之前 single-problem 模式跑出的 Library re-exports 仍在 `Library/Misc/`、
包含 cantor_xi_measure、compactness、gen_generates、inner_zero_iff_smul、
proj_nonexpansive、sylvester_gallai 共 6 項。這些 run 過 framework gate
（單 problem 模式下 gate 正確）、kernel-verified。
