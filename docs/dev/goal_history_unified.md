# Goal history: unified event-as-audience-declarer interface

Status: planned (2026-05-06). Replaces STATUS.md item 8 once implemented.

## 動機

當前 Context.md 有 4 個失敗相關 section（`## Past attempts on this goal` / `## Past decompositions that failed Verify` / `## Builder declines` / `## Prior strategies that died`），分散、命名不齊、kind-asymmetric gating（Builder vs Backward 看到不同子集）。SG g142 case 實證：Backward 重試時 inline 完全看不到自己 3 次 `lake_build_error` + `parse_proposal_fail`，只能靠主動 Read companion 檔。

問題本質不在「規則錯」，在於**「kind-as-router」設計把 audience 決策 hard-code 在 renderer**：每個 section 的可見性由 router 的 `show_attempts = kind in (None, "builder")` 之類 hard-code。

加新 pipeline kind（Forward / Generalizer / Refuter / Strategist）= 重新審視全部 router；audience 邏輯散落框架各處；無法做 per-event nuance。

## 設計核心：event-as-audience-declarer

決策權**從 router 搬到事件本身**。新事件類型自己宣告 audience，renderer 純粹 collect + filter + project。

```
event_contribution(must_see, optional)
  must_see: dict[event_type → digest]   # 直接 inline 注入到 Context.md
  optional: pointer to companion files  # on-demand 深查
```

兩層：
1. **必看（直接注入）**: pipeline 端只看 must_see；事件端宣告自己對誰是 must_see
2. **選看（指引）**: inline 列出 `companion files: PAST_DIRECT_ATTEMPTS.md, ...`，agent 主動 Read

## v1 scope

只覆蓋當前 Context.md 的 [C] 失敗歷史群組 + decline records：

| 既有 section | 對應的 event type |
|---|---|
| `## Past attempts on this goal` | `direct_attempt` (dead_attempts row, target_kind='Goal') |
| `## Builder declines` | `direct_attempt` 內 `failure_reason='agent_declined'` 子類 |
| `## Past decompositions that failed Verify` | `verify_failure` (strategy lake build 不過) |
| `## Prior strategies that died` | `dead_strategy` (cascade-shelve / F16 inward kill) |

decline records 不獨立成 event type — 是 `direct_attempt` 的 `failure_reason` 區分。

不覆蓋（v1 不動）：
- Goal context 群（statement / sandbox / strategy naming / parent goal）
- Resources 群（Manifest hints / forbidden / strategic notes / Library / Playbook）
- F55 progress note（性質是 future hint 不是 past failure，保持獨立 section）

未來考慮（**不該在 v1 做**）：
- Resources 改用同介面：audience 不會 vary，無 ROI
- Strategist 訂閱 全部 must_see：要做但等 Strategist 引入時再做
- 多層 priority tier：v1 只兩層，避免過早分類

## 統一 section 命名

當前散落 4 個 header → 合併為單一 umbrella `## Goal history`（不用 `## Failure history` — decline 不是 failure；未來其他 event type 可能也不是 failure）。

子結構（type-bucket 排序，桶內最新優先）：

```
## Goal history

### Direct attempts on this goal
（per-row digest，混含 lake_build_error / parse_fail / agent_no_response /
  forbidden_lemma / naming_violation / patch_signature_mismatch /
  agent_declined / agent_infeasible / spawn_fast_fail）

### Strategies that decomposed this goal but had a sub-goal shelved
（item 12 fix 的 root cause excerpt 內容；cascade-shelve cases）

### Sibling decompositions that failed Verify
（strategy 自身 lake build 過不了；audience 通常 Backward）

完整內容: PAST_DIRECT_ATTEMPTS.md / PAST_DEAD_STRATEGIES.md / PAST_VERIFY_FAILURES.md
（empty 子 section 整段省略）
```

<!-- 待重審 -->
<!-- ## Audience 矩陣

依事件性質而非 pipeline kind：

| Event 類型 | Builder must-see | Backward must-see |
|---|---|---|
| `tactic_try_exhausted` (direct) | ✓ | ✓ |
| `lake_build_error` (direct) | ✓ | ✓ |
| `agent_no_response` (direct) | ✓ | ✓ |
| `parse_proposal_fail` (direct) | ✓ | ✓ |
| `forbidden_lemma` (direct) | ✓ | ✓ |
| `naming_violation` (direct) | ✓ | ✓ |
| `patch_signature_mismatch` (direct) | ✓ | ✓ |
| `agent_declined` (direct, subtype) | — | ✓（接手 trigger） |
| `agent_infeasible` (direct, subtype) | ✓ | ✓ |
| `spawn_fast_fail` (direct) | — | —（framework signal，無 actionable）|
| `dead_strategy`（cascade-shelve）| ✓ | ✓ |
| `verify_failure`（sibling strategy verify 不過）| —（Builder 不拆解）| ✓ |

**axis 從「kind-based」改成「directness-based」**：直接於這個 goal 的事件都 must-see；跨 strategy 的看 audience。 -->

## 實作前置：pipeline 分檔

當前 `pipeline/__init__.py` ~1100 行 Builder + Backward 混雜。先拆：

```
pipeline/
  __init__.py       ← 共用 helpers + re-export
  builder.py        ← run_builder + Phase 1/2 邏輯
  backward.py       ← run_backward + decomposition + sub-goal placement
  _lake.py          ← 已存在（不動）
  _skeleton.py      ← 已存在（不動）
  events.py (新)    ← event-as-audience-declarer 介面
```

每個 pipeline 檔在自己 lifecycle 內 emit 事件。`compile_context` 在 renderer 端 collect + project。

未來 `forward.py` / `generalizer.py` / `refuter.py` 是新檔，不是 `__init__.py` 多開 if-branch。

## 設計細節

### Push vs hybrid audience

v1 用 **push**：event 自己宣告 audience，renderer 純 filter。

未來如有需要可升級 hybrid（pipeline 端 explicit opt-in 補看），但 push 已涵蓋觀察到的場景。

### 事件不是新 store

事件是 DB row 投影出來的（dead_attempts row → event object），不要建立 parallel event log。renderer query DB → transform 成 event 物件 → filter → render。

### Companion file 不合併

PAST_*.md 各自服務不同 event 類型，內容性質差很大（lake stderr vs PROPOSAL.md vs counterexample）。合一只是名字變短，內容仍要分塊。

可重命名對齊：
- `PAST_ATTEMPTS.md` → `PAST_DIRECT_ATTEMPTS.md`
- `PAST_BACKWARD.md` → `PAST_VERIFY_FAILURES.md`
- `PAST_DEAD_STRATEGIES.md` → 保留（已 OK）

### Empty sub-section 處理

當某 event type 在這個 goal 上沒任何 row，inline 整段省略（不顯示 `(none)`）。companion file 也不寫（避免空檔污染 sandbox）。

### F55 progress note 不入介面

性質是 future hint（killed spawn 留下的 starting sketch），不是 past event。維持獨立 section、位置可考慮提到更顯眼處（例如 umbrella 之外、緊接 Goal context）。

## 與其他 TODO 的關係

- **Item 11 (cross-branch dedupe)** 已完成（commit 865655d），不影響本 refactor
- **Item 9 (`first|...`)** 已完成，不影響本 refactor
- **Item 10 (lake instrumentation)** 不交互
- **Item 12 (bridge lemma layer)** 不交互
- **將來 Strategist**：本介面對 Strategist 友善 — Strategist 訂閱全部 must_see → 自動取得 problem-level 失敗結構，不必另寫 inventory query

## 實作順序

1. **Pipeline 分檔**：`pipeline/__init__.py` 拆 `builder.py` + `backward.py`，共用 helpers 留原檔。所有測試通過。Commit。
2. **Event interface 雛形**：`pipeline/events.py` 定義 event 投影函數（DB row → event object），`compile_context` 改用此介面。section 名稱先維持原樣。
3. **Renderer 重組**：合併 4 個 section 為 `## Goal history` umbrella。companion file 重命名。測試 fixtures 連動更新。
4. **Decline records 整合**：取消獨立 `## Builder declines` section，內容歸入 `### Direct attempts on this goal`。
5. **跑 SG 驗證**：對照 `sg-opus-proved-2026-05-06` baseline 看 wall-clock + g142-class case 是否真避開重複錯誤路線。

每步獨立可 commit。風險最大是步驟 3（測試假設大量 section 命名），需先盤點 grep `_section_*` + fixtures。

## 開放決策點

- Section 命名：`## Goal history` vs `## Past events on this goal` vs 其他
- companion file 是否真改名（純 cosmetic、可不動）
- 步驟 4 的 decline records 整合是否同 commit / 拆 commit
