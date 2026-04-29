# Asterism v2 — Current Status

寫於 2026-04-29 22:42。Compaction-safe handoff note.

## Milestone 1 已達成（首次）

Daemon `b6gflqxjn` 在 22:00:17–22:15:42 完整證出 wilson_main：

```
goals: main proved, main_sub_1 proved, main_sub_2 proved, main_sub_3 proved
strategy 1 succeeded
axioms: [propext, Classical.choice, Quot.sound]   ← 全在 Manifest whitelist
wall-clock: ~15 min
1 BUG fixed mid-run: lake env lean → lake build <module>
```

Milestone 1 通過條件 5 條達 4/5（Python 行數 1223 超 400 目標、但 < Hadamard 1500-1800、仍是進步）。

## Long-term cleanup 設計實作中（驗證跑）

Daemon `bc56rxf5t`（22:25 起跑）是驗證以下設計：

1. **`dead_attempts.artifacts JSON`** — 完整保留 agent 所有產出檔案（Context/PROPOSAL/patch/new_*）、不再 filesystem 副本
2. **`pipelines` 表只 INSERT 已 finished row** — 無 'running' 狀態、daemon 死掉重啟無殭屍
3. **`.attempts/<pid>/` 純 ephemeral** — pipeline 結束無條件 rmtree

最終結果（22:56）：daemon 30 min budget exceeded、4 次 Backward 全 fail、wilson 仍 open。
- #1 (39af939b) 22:25-29 forbidden_lemma (用 ZMod.wilsons_lemma)
- #2 (9c1087ab) 22:30-36 lake_build_error（Context 看 #1 → 4 sub-goal 含 involution、Lean compile 失敗）
- #3 (a2470f8a) 22:36-46 timeout 600s（Context 看 #1+#2、reasoning 過深沒寫 PROPOSAL）
- #4 (e9e86e9a) 22:46-56 timeout 600s
- daemon clean shutdown ✓、`.attempts/` 空 ✓、pipelines 4 finished rows 無 running ✓

**長期 cleanup 設計 5 點全綠**（finished-only pipelines + ephemeral .attempts + dead_attempts.artifacts JSON + timeout 偵測 + clean shutdown）。

**Wilson 沒 proved 的根因不是 cleanup design**：是 Context.md 累積 prior_failures 注入 → agent 設計越複雜 → reasoning 過深 → timeout。前輪（b6gflqxjn 22:00 fresh Context）一發 proved 對照可見。

**下次跑 OR 並行就能 cover**（同 goal N 條 Strategy 並行、各自用 spawn 時 snapshot 的 Context、不遞迴病態）。已記到 architecture.md §12.1。

**Asterism A7 改進實證**：Backward #2 的 PROPOSAL.md 開頭引用 #1 失敗（雙刃劍：好處在於 agent 真的學到、壞處見上方 reasoning 過深）：
> "Attempt 1 decomposed the core Wilson fact as a single sub-goal and Builder proved it with ZMod.wilsons_lemma — a forbidden lemma. This attempt breaks that same core into two strictly algebraic sub-goals."

agent 真的看 Context.md 注入的 dead_attempts 並調整策略。Hadamard `Dead/` 只 rename 檔不註記 reason、agent 看不出失敗點；Asterism artifacts JSON + failure_reason enum 補上這條。

## 架構文件

`docs/architecture.md` 是 SoT。約 320 行、§1-§13 完整覆蓋設計決策 + 「不做」清單 + Milestone 通過條件。

## 已決策（架構討論點）

- Manifest.md hints markdown only、不複製進 DB
- Manifest 寬 best-effort parse、缺欄位 default + warning
- Tooling/ 純重寫（不借 Hadamard 代碼）；< Hadamard 行數
- Shelve 判斷在 cascade、不在 next_worker_kind
- Pool size 預設 4、`ASTERISM_POOL=N` env 可覆蓋
- `proofs/` flat layout（≤30 個 L 檔）
- Worker 單次 timeout 10 min

## 未提交 git

整個 Asterism repo 還沒 git init、沒 push 上去。前一個 v1 commit 留在 GitHub `andersonwu2000/Asterism` 但 v2 完全是新代碼。

## 下一步

1. ~~等 bc56rxf5t~~（done; cleanup 驗證通過、wilson 沒重現 proved 但根因清楚）
2. **Git init + 第一個 commit** ← 進行中
3. 開放 OR 並行（架構 §12.1）— 解 Context 累積病態 + hedge timeout 風險
4. 第二個 problem（compactness or sg）測多 problem 平行

## Tooling 模組行數

```
Tooling/__init__.py        0
Tooling/db.py            ~330  (含 schema + helpers)
Tooling/manifest.py      ~150
Tooling/agent.py         ~130
Tooling/pipeline.py      ~290
Tooling/dispatcher.py    ~260
Tooling/cli.py            ~95
Tooling/prompts/*.md       ~80
total Python             ~1255
```
