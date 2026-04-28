# Phase 6 — Library + Multi-Problem

## 目標

P1–P5 都在單 Problem 內運作。P6 把框架擴張到 multi-Problem：跨 Problem 共用 Library、global single-reactor 對所有 Problem 同時處理、META.md axiom basis 驗證在跨 Problem import 時生效。
啟用 P1 預留的 `library_index` table、Library/Theorems/proved.lean 自動 promotion、Library/Counterexamples + Library/Constructions json 補 indexing、META.md `axioms` 強制宣告 + 跨 Problem axiom 一致性檢查。
**核心 mechanic**：兩個 Problem，第一個證出來的 lemma 變 Library entry，第二個 Problem 透過 `import` 取用、且 META.md axiom basis 必須 cover 第一個 Problem 用到的全集。

## Scope

### In

- **Multi-Problem global reactor**（v3 §6 Multi-Problem orchestration boundary）
  - Scheduler 是全域單 reactor、不是 per-Problem
  - Queue + pool 全 Problem 共享、Problem 之間競爭 slot
  - Structural refill BFS 對所有 Problem 跑（goals table filter `commit_state='live'`）
  - cascade per-Goal、不跨 Problem 連動
- **Library/Theorems/proved.lean 自動 promotion**（v3 §6 Library promotion 段、impl §3.1）
  - **走 P3 cascade dispatch table**：P6 在 dispatch table 註冊新 trigger entry `(pipeline_kind=any, outcome=proved/classical/root) → [LibraryPromotion]`，**不動 reactor 主迴圈**。P1/P2 的 cascade 規則（strategies.succeeded → goal proved）保持不變
  - cascade 偵測 `status='proved'` + `answer_data.type='classical'` + `origin='root'` + trust_set 通過 `Library.whitelist` → append re-export 行
  - file lock：fcntl on Unix、sqlite advisory lock 跨 OS
  - `library_index` INSERT；命中既有 name → first-write-wins + warning event
  - lake build verify；fail → revert（刪 append + DELETE row + 父 Goal status 退 attempting + dead_attempts）
  - re-export 行格式：`theorem <problem>.<slug> := <fully-qualified-source-name>`，其中 source name 由 spike-024 結果決定（Goal .lean 內 theorem name + namespace path 規則）；可能需 cascade rename 或 user 命名約束
- **Library/Counterexamples + Library/Constructions json 補 indexing**（impl §3.2 / §3.3）
  - P4/P5 已寫 json，但沒 INSERT library_index row（當時 table 不存在）
  - P6 啟用 INSERT；對 silver→gold 升級走 UPDATE 不重複 INSERT
  - 寫 `asterism library reindex` migration tool 回掃既有 json（P4/P5 demo 累積的）補 row
- **`library_index` table 啟用**（v3 §9.1）
  - composite PK (layer, name)
  - layer enum: Theorems / Counterexamples / Constructions
  - source_root_id FK goals、committed_at ts
- **META.md axiom basis 完整驗證**（v3 §8.2、impl §5.0）
  - 強制宣告（無框架預設繼承）
  - scheduler 啟動時對每個 Problem 解析 META.md、驗 `axioms` 欄位存在；缺則 reject load + emit alert
  - 對應 cascade verdict accept rule 改用該 Problem 的 axioms（取代 P2 的硬編碼）
- **跨 Problem import 一致性檢查**（v3 §7.1 + §8.2 段「該 Problem 的所有依賴 X 的結果...consumer 必須在自己 META.md 的 axioms 也含 X 才能用」）
  - 機制：Problem A 證出 lemma 用了 axiom set S_A、Problem B import 該 lemma 時，B 的 axioms 必須 ⊇ S_A 內 mathematical 層 axiom
  - **P6 採 CLI 手動觸發**：`asterism library check-deps` 包裝呼叫 `tools/check_axiom_coverage.lean`（後者是純 Lean exe、scan Library 各 entry trust_set + 比對所有 Problem META.md.axioms）。**不做 lake build 階段自動 hook**（留 P7+）。reviewer 不要寫 lake plugin
  - **違反時的觸發鏈**：
    1. `library check-deps` exit 非 0 + 印違反清單 + emit alert event
    2. **user 手動** `asterism problem pause <P>`（emit `control_signal(action=pause, scope=problem, target=P)`）
    3. 之後 cascade 因 Problem 在 paused 狀態跳過該 Problem 的 enqueue
  - **不**走「check-deps 自動 pause」（P6 簡化、保 user 介入）
- **Per-Problem proved.lean re-export**（v3 §9.2）
  - `Problems/<n>/proved.lean` 該 Problem 內**所有 origin** 的 status='proved' Goal re-export（root / backward / forward / generalizer / refuter_negation / construction_witness 全收，無論 origin 為何）
  - cascade Goal proved 時（不限 root）append 此檔
  - 跟 Library/Theorems/proved.lean（**限** origin='root'）區分
- **derived_from cascade 限同 Problem 邊界**（架 §6 Multi-Problem 段「cascade per-Goal、不跨 Problem 連動」）
  - schema 不擋跨 Problem `derived_from` FK，但 cascade rule 預設 `WHERE problem = ?` filter——derived_from cascade 只在同 Problem 內升 silver→gold；跨 Problem 升 gold 行為**未定義**（P6 reject、emit alert）
  - 預防 P5 升 gold cascade 在 multi-Problem 時意外跨 Problem 連動
- **Trust set kind 完整 enum**（v3 §7.1）
  - `lean_axiom` / `computational` 兩 kind 在 P4/P5 已上；P6 不擴 kind，但補上 `confidence` 欄位（lean_axiom 永遠 1.0、computational 預留未來計算評估）
- **CLI 擴**：
  - `asterism problem list` 列所有 Problem + 各自 axioms 集合
  - `asterism library list [--layer Theorems|Counterexamples|Constructions]` 列 library_index
  - `asterism library check-deps` 跑跨 Problem axiom 一致性
  - `asterism library reindex` 回掃 json 補 library_index
  - `asterism scheduler force-clear` 手動清 stale schedulers row（liveness false-positive 救援）
  - `asterism goal add --imports <comma-separated-paths>` 額外 import 宣告（P6 新 flag，跨 Problem 重用 lemma 必需）；如 `--imports "Problems.A.Proved,Problems.B.Proved"`
  - `asterism problem pause <p>` / `asterism problem resume <p>`：emit `control_signal(action=pause/resume, scope=problem, target=<p>)`；scheduler 對 paused Problem 跳過 enqueue（cross-Problem axiom check 違反時 user 介入用）
  - `asterism library audit`（**P6 stub**）：未來 CLI for Mathlib upgrade audit（重跑 #print axioms 對所有 Library entry 比對 trust_set snapshot）；P6 預留 stub exit 1 + 印「not implemented; tracked in P7+」+ TODO；避免 P7 忘記
- **DB schema（啟用 P1 預留）**：
  - `library_index` table：P1 schema 已建、P6 起真實寫入
  - `schedulers` liveness：P1 已建 table 與 last_heartbeat 欄位、P6 啟用檢查邏輯（startup heartbeat 比對）
- **Cache invalidation 對 library**（impl §2.3）
  - Library/Theorems/proved.lean append 或 Library/Counterexamples / Constructions 寫入 → DELETE search_cache WHERE scope LIKE '%library%'
  - P3 cache 機制已建、P6 補 library 觸發點

### Out

- Forward / Generalizer / Strategist（P7）
- Library 對未來 Conjectures/ 層的 promotion（v3 §6 註明留 deferred）
- Library promotion 的 promotion judge agent（自動 promote 即可）
- 跨 Problem 自動 import suggestion（人類自己寫 `import Problems.X.Proved`）

## Demo

```bash
# Problem A：證一個 lemma
asterism init --problem list_lemmas
# META.md axioms = 三公理

asterism goal add --problem list_lemmas \
  --slug append_nil_eq_self \
  --kind theorem \
  --spec "∀ l : List Nat, l ++ [] = l"
# --spec flag 自 P2 起為統一 flag，已替代舊 --statement

asterism run
# 跑通 → list_lemmas.append_nil_eq_self proved
# Library/Theorems/proved.lean append 一行
# library_index INSERT (layer=Theorems, name='list_lemmas.append_nil_eq_self')
# Problems/list_lemmas/proved.lean 也 append

# Problem B：用 Problem A 的 lemma
asterism init --problem sort_demo
# META.md axioms = 三公理（跟 list_lemmas 對齊）
# Defs.lean 範本 + user 加 sort 定義：
#   import Mathlib
#   def sort (l : List Nat) : List Nat := l.mergeSort (· ≤ ·)

asterism goal add --problem sort_demo \
  --slug sort_preserves_length \
  --kind theorem \
  --spec "∀ l : List Nat, (sort l).length = l.length" \
  --imports "Problems.list_lemmas.Proved"

asterism run
# Backward 拆解時 find_lemmas 透過 search subsystem (library scope) 撈到 list_lemmas.append_nil_eq_self
# agent 寫的 sub-Goal proof 用此 lemma → Builder lake build 通過（因為 import 已宣告）
# Cascade up → sort_preserves_length proved

# 跨 Problem axiom 一致性
asterism library check-deps
# 預期：sort_preserves_length 依賴 list_lemmas.* → check 兩 Problem 的 axioms 都 cover → pass
```

對立 demo C（**single-Problem accept rule reject**——P2 機制延續）：

```bash
# Problem C：axioms 拿掉 Classical.choice，但用了 Mathlib 內某個依賴 choice 的 lemma
asterism init --problem no_choice
# META.md axioms = [propext, Quot.sound]（拿掉 Classical.choice）

asterism goal add --problem no_choice \
  --slug needs_choice_demo --kind theorem \
  --spec "..."

# cascade 構造 trust_set 含 Classical.choice → accept rule 比對 Problem.axioms 缺 → reject
#   alert + Goal 留 attempting + dead_attempts 寫「trust_set rejected: Classical.choice」
#   pause control_signal emit
```

對立 demo D（**cross-Problem axiom coverage reject**——P6 新機制，配 acceptance #4b）：

```bash
# Problem A_rh：axioms 含 mathematical 假設 RH (riemann_hypothesis)，證了一個依賴 RH 的 lemma
asterism init --problem rh_consequences
# META.md axioms = 三公理 + riemann_hypothesis
# 注入 + 證 → Library/Theorems 含 rh_consequences.* entry，trust_set 含 riemann_hypothesis

# Problem B_naive：axioms 不含 RH，import A_rh 想用其 lemma
asterism init --problem rh_naive
# META.md axioms = 三公理（缺 riemann_hypothesis）

asterism goal add --problem rh_naive --slug uses_rh_lemma --kind theorem \
  --spec "..." --imports "Problems.rh_consequences.Proved"

asterism library check-deps
# 預期：exit 非 0，印「rh_naive imports rh_consequences.* but axioms 缺 riemann_hypothesis」+ alert event
# user 手動：asterism problem pause rh_naive
# 之後 cascade 跳過 rh_naive；user 修 META.md 補 riemann_hypothesis 後 problem resume
```

## Acceptance criteria

0a. **Demo A+B end-to-end**：上面 §Demo 主 bash（Problem A → B 跨 Problem import）跑完、最終 sort_preserves_length proved + Library/Theorems 含兩 entry。**single sanity gate**
0b. **Demo C end-to-end**：對立 demo C bash 跑完、Goal 留 attempting + dead_attempts 寫「trust_set rejected: Classical.choice」+ pause event emit
0c. **Demo D end-to-end**：對立 demo D bash 跑完、`library check-deps` exit 非 0 + alert + 手動 problem pause 後 rh_naive cascade 跳過
1. **Multi-Problem reactor**：兩個 Problem 各注入 1 個 Goal → 同 reactor 內 BFS 都看到、enqueue 兩條 Backward、共享 atomic pool
1a. **Multi-Problem stress**：5 個 Problem 各 3 個 root（含 theorem / conjecture / construction 混合）並發跑 30 min。**Pool config**：`P=8`（atomic pool 拉高、避免 starvation 假象）+ `P_continuous=4`（每 Problem 至少 1 個 continuous slot）。**fairness 驗法**：30 min 內每 Problem 至少有 1 個 atomic + 1 個 continuous pipeline 在 spawn 過（SQL `SELECT COUNT(DISTINCT problem) FROM pipelines WHERE started_at > <begin>` = 5）；無 deadlock；無單一 Problem 連 10 min 無新 spawn
2. **Library/Theorems promotion**：Demo Problem A 跑通後，`Library/Theorems/proved.lean` 含 re-export 行、`library_index` 有對應 row、`lake build Library` pass
3. **跨 Problem import**：Demo Problem B 透過 `import Problems.list_lemmas.Proved` 用到 A 的 lemma、Backward find_lemmas 透過 search (library scope) 撈到、Builder lake build 通過
4a. **跨 Problem axiom check pass**：兩 Problem axioms 對齊（都三公理）→ `asterism library check-deps` exit 0、無 alert
4b. **跨 Problem axiom check reject**（fixture-based，不在 demo 內、demo D 走完整鏈）：人為 setup Problem A_rh axioms 含 RH + Problem B_naive axioms 不含、B 內 Goal 含 `--imports A_rh.Proved` → `library check-deps` exit 非 0 + 印違反清單 + alert event。**注意 #0c demo D 已驗端到端鏈（含 user 手動 pause + cascade 跳過）**，#4b 只驗 check-deps 自身輸出
5. **Per-Problem proved.lean 收所有 origin**：Problem A 內 sub-Goal proved + 人為 setup origin='construction_witness' Goal proved → 兩者都進 Problems/list_lemmas/proved.lean、Problem B import 後可用（驗收集規則蓋全 origin、不限 root）
6. **First-write-wins**：人為對同 lemma_name 重複 promote → 第二次 INSERT fail + warning event + 不 append 重複行
7. **Promotion fail revert**：用 `LIBRARY_BUILD_FAULT=1` env hook 強制 lake build Library 回 fail → 自動 revert（append 行刪除 + library_index DELETE + 父 Goal 退 attempting + dead_attempts 寫入）
8. **library reindex migration**：對 P4/P5 demo 累積的 json 跑 `asterism library reindex` → library_index 補齊對應 row
9. **Library.whitelist 過濾 RH-dependent**：Problem 內 RH-dependent proved（axioms 含 riemann_hypothesis）→ trust_set 不通過 `Library.whitelist`（典型三公理）→ **不**進 `Library/Theorems/proved.lean`、但進 `Problems/<n>/proved.lean`（驗 whitelist 對 mathematical axioms 確實過濾）
10. **schedulers liveness**：用 `--bypass-startup-check` flag（test-only，跳過 CLI 早期 single-instance check、讓進到 liveness check 階段）啟第二個 scheduler instance → liveness check 偵測 first instance heartbeat 仍新 → reject 啟動 + 印錯訊息（**驗 liveness check 真的有效，不是 CLI 早期攔截**）
11. **scheduler force-clear 救援**：人為 mock scheduler crash（kill -9）→ 90s 後 schedulers row 仍存在但 heartbeat 過期 → 第二實例啟動被 stale row 擋（reject）→ 跑 `asterism scheduler force-clear` → row 清掉 → 第二實例重啟可成功

## 依賴

### 前置 phase

- P1–P5 完成

### 必跑 spike

spike 編號接 P5 後（P5 已用至 spike-020；spike 編號集中由 `docs/spikes.md` 配發）：

- **spike-021 lake build Library 子模組速度**——對 N 個 promote 後的 Library/Theorems/proved.lean 跑 lake build，看時間隨 N 線性還是更糟。決定是否需 incremental build 機制
- **spike-022 fcntl on Windows**——Windows 不支援 fcntl，sqlite advisory lock 是否真能跨 OS 一致？
- **spike-023 跨 Problem import 行為**——`import Problems.list_lemmas.Proved` 在 lake 中是否需要顯式 build dep 宣告？影響 Problem META.md / lakefile 整合
- **spike-024 跨 Problem theorem name 解析**——Goal .lean 內 user/agent 寫 `theorem add_zero_simple : ...`，跨 Problem import 後完整 namespace path 是什麼？`Problems.list_lemmas.append_nil_eq_self.add_zero_simple`？還是 cascade 自動加 `<problem>.<slug>` namespace wrapper？影響 §In re-export 行格式（目前寫 `theorem <problem>.<slug> := <problem>.<slug>.theorem` 的 `.theorem` suffix 來源不明）；可能需要 cascade rename 或 user 命名約束

## 引入元件

### DB schema（啟用 P1 預留）

P1 schema 已建全 schema（codex review #12 決策）。**P6 不擴 schema**——只是開始消費：

- `library_index` table：P1 schema 已建、P6 起真實寫入（composite PK (layer, name)）
- `schedulers`：P1 已建 table 與 last_heartbeat 欄位、P6 啟用檢查邏輯（startup heartbeat 比對）

### Tooling 新增

- `Tooling/library/promotion.py`：Library/Theorems append + library_index INSERT + revert 邏輯
- `Tooling/library/reindex.py`：CLI `asterism library reindex`
- `Tooling/library/check_deps.py`：CLI `asterism library check-deps`（包裝呼叫 `tools/check_axiom_coverage.lean`）
- `Tooling/library/audit.py`：CLI `asterism library audit` **stub**（exit 1 + "not implemented; tracked in P7+"）
- `tools/check_axiom_coverage.lean`：跨 Problem 一致性檢查 Lean exe
- `Tooling/locks.py`：fcntl + sqlite advisory lock 跨 OS 包裝
- 擴 `Tooling/cli.py`：`problem` 子命令（list / pause / resume）、`library` 子命令、`scheduler force-clear`
- 擴 `Tooling/meta.py`：跨 Problem axiom 一致性檢查邏輯

### Test infrastructure

新增 env hook（對齊 P1 `COMMIT_FAULT` 風格、總清單見 `docs/dev/test_hooks.md`）：

- `LIBRARY_BUILD_FAULT`：boolean，強制 lake build Library 子模組回 fail（給 promotion revert acceptance #7 用）

新增 CLI flag（test-only）：

- `--bypass-startup-check`（取代 P6 草稿的 `--allow-multi-instance`）：scheduler 啟動跳過 CLI 早期 single-instance 攔截、讓進到 liveness check 階段；liveness check 仍正常擋（給 acceptance #10 用）

### Cascade table 擴行

- Library/Theorems promotion trigger（P6 才啟動）
- Library/Counterexamples + Constructions index INSERT（P4/P5 寫 json + P6 補 index）
- Per-Problem proved.lean append on any proved Goal

### META.md `forbidden_lemmas` blacklist（P6.x patch 21）

per-Problem META.md 可宣告：

```yaml
forbidden_lemmas:
  - <FullyQualifiedLemmaName>
  - ...
```

**硬閘門**（不是 prompt 軟提示）：cascade 在 trust_set + accept_rule 之後 grep strategy file 文字、若任一 forbidden lemma 出現 → mark strategy dead + 寫 `dead_attempts.outcome='forbidden_lemma_used'`、UPDATE goal status='open' 強制 BFS 重派 Backward。下次 Backward 的 `failure_replay` 撈到此 entry、agent prompt 看到 `forbidden_lemma_used: <names>` → 不二犯。

對 prompt 是 hint、對 framework 是硬限制。給 Hadamard-style「人為設計拆解結構」用：禁直接同名 lemma → agent 必須走 Path B decomposition。

實現：text grep（word-boundary regex）、不是 Lean walker。注意點：
- 名稱在 comment 也會 match（false positive）
- substring match 收斂用 `(?<![\w.])lemma(?![\w])` lookahead 避免誤抓 `Real.uncountable_univ` 當 `Real.uncountable` 命中
- `by simp` / `by decide` 等 tactic 內部用 forbidden lemma 不會被 grep 抓（proof term 不在 .lean 文字內）— 是已知限制、未來可升級成 Lean walker walk transitive 引用

### Strategy file 為 staging、Goal file 為 canonical（P6.x patch 22 + 23 two-phase commit）

Backward Path A leaf-bypass 不直接寫 goal `<slug>.lean`、而寫 sibling `_strategy_<pid>.lean`（自己的 namespace `Problems.<p>.Goals.<id_seg>._strategy_<pid>`、不撞 goal namespace）。Goal file 整 daemon lifecycle 維持 `:= by sorry` 直到：

1. Builder 驗 strategy file pass
2. trust_set 構造 + accept_rule pass
3. forbidden_lemmas 檢查 pass

三閘門全綠後 cascade `_finalize_goal_file_from_strategy`：
- 從 strategy file regex 抽 proof body
- 寫 canonical content（namespace `Problems.<p>.Goals.<id_seg>` + theorem `<slug>`）到 `<goal>.lean.tmp`
- `os.replace(.tmp, <goal>.lean)` atomic rename
- 刪 strategy file
- UPDATE strategies.lean_path = goal_lean_path

Goal file 從此是 canonical proven artifact、proved.lean re-export 從 goal file path 引、後續 sibling Goal 的 strategy 直接 `import Problems.<p>.Goals.<id_seg>.<slug>`。任一閘門 fail：strategy file 留檔給 operator inspection、goal file 不動（仍 sorry）、BFS 重派 Backward。

### Config

| key | P6 預設 |
|---|---|
| `Library.whitelist` | `{propext, Quot.sound, Classical.choice}` |
| schedulers heartbeat 間隔 | 30s |
| schedulers stale threshold | 90s |
| `forbidden_lemmas` （per-Problem META.md） | `[]`（無黑名單） |

## 任務序列

DB 端 P6 不需 schema migration（P1 已建全 schema）；任務序列只列實作動作：

1. **spike-021 / 022 / 023 / 024 跑完**——結果落 `docs/spikes.md`
2. **Locks 跨 OS**（`Tooling/locks.py`）：依 spike-022 結果決定 sqlite advisory or fcntl
3. **Library promotion 邏輯**（`Tooling/library/promotion.py`）：對齊 impl §3.1；re-export 行 source name 對齊 spike-024 結果
4. **Per-Problem proved.lean append on all-origin proved**：cascade hook（不限 root，含 construction_witness / refuter_negation 全收）
5. **跨 Problem META.md axiom 解析升級**（`Tooling/meta.py`）：scheduler 啟動掃所有 Problem
6. **`tools/check_axiom_coverage.lean`** Lean exe + Python 包裝（`Tooling/library/check_deps.py`）；P6 採 CLI 手動觸發、不寫 lake hook
7. **derived_from cascade rule 加 same-problem filter**：升 silver→gold 路徑限同 Problem，跨 Problem reject + alert
8. **CLI 擴**：`problem list / pause / resume`、`library list / check-deps / reindex / audit (stub)`、`scheduler force-clear`、`goal add --imports <comma-separated>`、`--bypass-startup-check` flag
9. **`LIBRARY_BUILD_FAULT` env hook**（test-only）
10. **Cache invalidation 對 library 觸發點補上**（P3 鉤子已建、P6 接 trigger）
11. **schedulers liveness check 啟用**：startup 拒絕第二實例
12. **Library reindex migration 跑過 P4/P5 既有 json**
13. **Demo Problem A + Problem B 跑通 + acceptance test**
14. **對立 demo C / D 跑通**（C：single-Problem accept rule reject；D：cross-Problem axiom coverage reject + 手動 problem pause + cascade 跳過）
15. **移除 `--statement` deprecated alias**（P5 引入時保留為 alias、P6 移除）：刪 `Tooling/cli.py` 內 `--statement` flag 與 deprecation warning；CLI help 不再列；任何 P5 期間 user 還用此 flag 改 reject + 印「flag removed; use --spec」

## 測試

- **Unit**：library_index INSERT first-write-wins
- **Unit**：Library promotion lake build fail 後 revert 完整性
- **Unit**：META.md `axioms` 缺欄位 reject load
- **Unit**：跨 Problem axiom check pass / fail 各 case
- **Unit**：Cache invalidation library 觸發點
- **Unit**：schedulers liveness reject 第二實例
- **Integration**：Problem A → B 跨 Problem import demo
- **Integration**：對立 demo（axiom 不一致 → reject + pause）
- **Integration**：library reindex migration
- **Integration**：multi-Problem 並發（兩個 Problem 同時跑 conjecture demo from P4，互不干擾）
- **Stress**：5 個 Problem × 各 3 root 同時跑，pool 公平性

## 風險與 open questions

- **fcntl on Windows**：spike-022 結果若 sqlite advisory lock 也不夠強，要 fallback 到 file-based lock（atomic rename 或 lock file）；可能會慢且 flakey
- **lake build Library 慢累積**：spike-021 結果若隨 N 平方成長，promote 100 個 lemma 後 build 半小時。應變：incremental Library build mode（只 build 新 append 部分）；或 Library 拆 sub-modules
- **跨 Problem axiom check 自動化 vs CLI 手動**：v3 spec 是「consumer 必須在 META.md cover」但沒明說自動觸發。P6 簡化做 CLI 手動 `library check-deps`；若實際使用流程顯示常忘了跑、要改成 cascade promotion 自動觸發
- **Per-Problem proved.lean 越寫越大**：每個 proved Goal 都 append，幾十個 Goal 後檔案大、lake build 慢。應變：sub-modules 拆（依 Goal namespace）；P7 處理
- **Problem B 透過 search (library scope) 撈到 A 的 lemma 但 axioms 不齊**：search 不分 axioms→ agent 提案後 Backward dedupe 會撈、Builder lake build 通過、cascade verdict 構造 trust_set 才 reject。Wasted compute。應變：search 預掃 trust_set 過濾、或 cascade 早期 reject。P6 留簡化版（cascade reject）+ alert
- **`Library.whitelist` 跟 `Problem.axioms` 概念混淆風險**：使用者要寫 META.md 時可能誤把 Library.whitelist 當 Problem.axioms 預設值。CLI `asterism init` 模板要清楚註解
- **schedulers liveness false-positive**：scheduler crash 時沒清 row → 第二實例啟動被 90s threshold 擋。應變：CLI `asterism scheduler force-clear` 手動解
- **Mathlib upgrade 對 Library 影響**：Mathlib 改了某個 lemma 的 axiom dependency → Library 內 import 該 lemma 的 entry 仍然有效嗎？trust_set 是 promote 當下 snapshot、不會自動更新。**P6 預留 `asterism library audit` CLI stub**（exit 1 + 印 "not implemented; tracked in P7+"），P7+ 補實作（重跑 #print axioms 對所有 entry、列已不一致的）。stub 落地避免 P7 忘記
