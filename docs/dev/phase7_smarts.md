# Phase 7 — Smarts

## 目標

P1–P6 完成框架核心能力（單/多 Problem、theorem/conjecture/construction、cache、Library promotion）。P7 是「優化層」：上 Forward / Generalizer / Strategist 三條 fuzzy-trigger pipeline，用 LLM-driven meta-coordination 提升 search efficiency 並啟用自動探索。
**核心新元件**：Strategist 真實 inject task、Forward 推下游 corollary、Generalizer 推上游抽象。
P3/P4/P5 算出來但無人消費的 signals（IH-trap / silver 卡升級 / construction plateau / blocked_pipelines 觸發）在 P7 都接上 Strategist。
**Demo 是雙跑對照**：同一 Problem 啟用 P7 前 vs 後，量化 search efficiency 改進（cascade speedup / token 節省 / Goal 早 shelve 比例）。

## Scope

### In

- **Forward pipeline**（pipelines.md §4）
  - 完整 stage 序列：`failure_replay` → `find_pattern`（local proved Goals as seed）→ `find_mathlib`（dedupe 用，避免 propose 已有）→ agent → self_verify → `dedupe (any)` → commit
  - seed pool 含 negation Goals（v3 §決策日誌「Forward seed pool 含 negation Goals」）
  - 觸發來源：Strategist inject only（無 structural refill 自動派）
- **Generalizer pipeline**（pipelines.md §8）
  - 完整 stage 序列：`failure_replay` → agent（讀 G、寫 G* 候選）→ self_verify → `dedupe (any)` → commit
  - 觸發來源：Strategist inject only
  - unproductive **不**寫 blocked_pipelines（保留 Strategist 反覆派彈性）
  - **無**自動 cascade（G* proved 不自動標原 G proved——需 Cluster typed relation 機制，留 P8+）
- **Strategist pipeline**（pipelines.md §5）
  - 完整 stage 序列：`failure_replay` → `inventory` → agent → self_verify (JSON schema) → commit
  - inventory metrics：per-Goal、per-subtree、全域 top-N（impl §6.4 SQL）
  - decisions enum：Refuter / Forward / Generalizer / Backward / Counterexample / ConstructionSearch / Shelve
  - 觸發：每 K_strategist=P×2 個 pipeline_finished 累計 + cooldown
  - inject 上限：M_strategist=5 per run
  - decision payload 可覆寫 budget / range / mutation operators
  - **decision payload `model?` / `provider?` 欄位**（架 §8.3 三層 model 解析的最高優先層）：對 stuck Goal 加強用 opus、或指定 fallback provider；缺則沿用 Problem META.md / 框架預設
- **Multi-Problem Strategist 視野策略**（v3 §6 Multi-Problem 段「Strategist inventory per-Problem 視野」）
  - 每次 Strategist 跑時 inject 一個 Problem id 進 prompt、inventory 只聚合該 Problem
  - 觸發時 round-robin 不同 Problem（**嚴格輪詢**，非 weighted）
  - **`K_strategist` 累計 global**（不分 Problem），達 K → cooldown 釋放後 round-robin 切下個 Problem
  - cooldown 是 global、non-overlapping：A 跑完 → cooldown 釋放 → B 排到下個 round-robin 位置 → 計數重新累計到 K → 觸發 → 切 C；如此循環
- **Strategist signal 接 P3/P4/P5 算出來的素材**（架構 pipelines.md §5 已列前 5 條；**第 6 條 blocked_pipelines 觸發為 P7 新增、需 PR 同步加進架構 pipelines.md §5**）：
  - **IH-trap**（pipelines.md §5）：Strategy 連續 ≥ 2 次 unproductive AND `parent_subgoal_max_similarity ≥ 閾值` → 強訊號 Refuter / Shelve
  - **Silver 卡升級**（pipelines.md §5）：G refuted/witness AND evidence 含 witness AND 對 G **已有 active Refuter 但連續失敗**（hard rule 已派過、仍卡）→ 弱訊號 inject 額外 Refuter（**hard rule 是 base case，此 signal 是加碼**——P4 silver-stuck hard rule 仍永久保留）
  - **Construction plateau**（pipelines.md §5）：active ConstructionSearch ≥ 20 代無 best_score 改進 → 弱訊號換 mutation operator 或 Shelve
  - **Construction 接近 target**（pipelines.md §5）：score ≥ target × 0.95 → 強訊號加碼 budget
  - **新形式化的 negation**（pipelines.md §5）：cascade 剛把 Goal 翻 refuted/classical（Refuter→Builder 鏈）→ 弱訊號 inject Forward on negation Goal
  - **Pipeline blocked_pipelines 觸發**（**P7 新增、待 PR 入架構**）：強訊號需 meta 介入；Strategist 評估 Shelve 整 Goal 或換角度
- **`evidence_updated` event 消費**：Strategist 在 prompt 內看到最近 `strategist.evidence_window=20` 個 evidence_updated，反思下個 decision
- **過去 decisions outcome 反思進 prompt**：SQL `SELECT d.decisions, p.outcome FROM strategist_decisions d JOIN pipelines p ON p.target_id IN (d.decisions targets) ORDER BY d.ts DESC LIMIT N` 撈最近 N 次 decision 與 downstream pipeline outcome、寫進 Strategist agent prompt（self_verify 看自己過去判斷是否有效）
- **strategist_decisions table 啟用**（v3 §9.1）
- **Cancellation 白名單擴**：加 Strategist Shelve action 對應的 cancel rule（同 Goal still-running 全部）
- **Cascade 規則「shelved」連鎖**：Goal shelved → cancel 同 Goal 仍 running 的所有 pipeline
  - **架構文件補丁**：v3 §6 cancellation 表只列 proved/refuted trigger、未列 shelved；P7 上線時順便 PR 加進架構表（`Verdict 觸發源 = Strategy dead 連鎖 Goal 退 open / shelved` 那行擴成「shelved 也 cancel」），保持 spec 與實作對齊
- **CLI 擴**：
  - `asterism config set <key> <value>` / `asterism config get <key>` / `asterism config list`——P7 起 framework config 部分 key runtime 可變更（依 category 分、見下）
  - `asterism strategist run-once` 手動觸發 Strategist（debug 用）
  - `asterism strategist decisions` 列最近 N 條 decisions + 後續結果（self-evaluation 視覺化）
  - `asterism strategist explain --last`：顯示最近一次 Strategist run 的 inventory snapshot + agent 寫的 reasoning + 為何 inject / 不 inject 各 decision（給人類調 prompt 用）
  - `asterism inventory <problem>` 跑 strategist inventory query 印出 metrics（不 inject）
  - `asterism fixture <name>`（test-only CLI，**跟 env fault hook 互補**——fault hook 強制 stage 失敗、fixture 注入預設狀態便於 acceptance test 起步）：如 `asterism fixture ih_trap` 建一個已 unproductive 兩次 + similarity ≥ threshold 的 Goal；`asterism fixture silver_stuck` 建一個 silver/witness 但無 active Refuter 的 Goal
- **Config runtime mutability category**（`config set` 對 restart-required 提示 user 重啟、對 immutable 直接 reject）：
  - **runtime mutable**（即時生效）：`strategist.enabled` / `K_strategist` / `M_strategist` / `K_digest` / `ih_trap_similarity_threshold` / `strategist.evidence_window`
  - **restart-required**（CLI 提示「set 成功但需重啟 daemon 才生效；in-flight pipeline 用舊值」）：`P` / `P_continuous` / `T_checkpoint` / `agent.providers` / `agent.fallback_chain`（基建容量 + provider chain）
  - **immutable**（`config set` 直接 reject + 提示「請編輯 config 檔 + 跑 `asterism library audit` 重評」）：`Library.whitelist` / `Problem.axioms`（政策性、retroactive 影響既有 Library entry 評估）

### Out

- Cluster typed relation（generalizer 自動 cascade 升級需要）→ 留 P8+
- Mathlib upgrade audit（P6 風險章節提的、P6 預留 stub `asterism library audit`）→ 留 P8+ 接 stub
- Cross-Problem axiom check 自動觸發（P6 採 CLI 手動 `library check-deps`、用 `problem pause`）→ 留 P8+ 升級成 cascade promotion 階段自動觸發
- Promotion judge agent（v3 自動 promote 即可，P6 已決）
- Token cost optimization
- 多 Strategist 並行（單 Strategist + cooldown 即可）
- Strategist signal 學習（從歷史 outcome 自動調 threshold）→ 留 P8+

## Demo

雙跑對照 demo（同一組 5 root，跑 3 次取中位數對照）：

```bash
# Demo D-baseline：P7 disable Strategist，跑 5 個 conjecture root（混真假，含 IH-trap / silver / 攻不動 / 一般 case）
asterism init --problem p7_demo
# 注入 5 root（fixtures 來源見 spike-021 baseline 文件）

asterism config set strategist.enabled false
for run in 1 2 3; do asterism run; done
# 量測每次：wall-clock、token、終態分布
# 預期：true conjecture 走 Backward 鏈成功，false conjecture 走 Counterexample silver→gold
#       但有些難命題 Backward 反覆 exhausted、無 Strategist 時不會主動 Shelve、永遠 attempting
#       （P3 in-memory cap 已被 P3 持久化版取代，blocked_pipelines 會擋 Backward 但不會 Shelve 整 Goal）

# Demo D-strategist：同 5 個 root，啟用 Strategist
asterism config set strategist.enabled true
for run in 1 2 3; do asterism run; done
# 量測：wall-clock、token、終態分布
# 預期改進：
#   - IH-trap Goal 提前 Shelve（不只 blocked Backward、整 Goal Shelve）
#   - 卡 silver 的 Goal 透過 Strategist「Silver 卡升級」signal 重派 Refuter → 升 gold
#   - 攻不動的 Goal Strategist 主動 Shelve（不再無限 attempting）
#   - 整體 cascade speedup（少花在無望分支）
```

第二個 demo：generalizer

```bash
# Goal G1 證了「∀ n : Fin 4, P n」、Goal G2 證了「∀ n : Fin 8, P n」
# Strategist 看 inventory 發現 root proved 結構相似 → inject Generalizer
# Generalizer agent 寫 G*: 「∀ n : Nat, P n」候選
# G* 入池 → normal Backward / Builder 攻擊
# 證了 → Library/Theorems append
```

## Acceptance criteria

0a. **Demo D-baseline + D-strategist 對照 end-to-end**：上面 §Demo 雙跑 bash 各跑 3 次取中位數，兩組結果產出 + Strategist 啟用後改進指標達標（pin 死 number 見 #16）。**Strategist demo single sanity gate**
0b. **Demo Generalizer end-to-end**：第二個 demo bash 跑通、G* 入池 + normal attack 進終態（proved 或 attempting）。**Generalizer demo single sanity gate**

### Strategist 行為

1. **觸發頻率**：跑 P×2=8 個 pipeline_finished 後 Strategist 在 atomic queue 出現一次（priority=high）
2. **Cooldown**：Strategist 跑時不重派；commit 完才重置
3. **M 限制**：單次 inject ≤ M_strategist=5 個 task
4. **decisions JSON schema**：commit 寫的 strategist_decisions row 通過 schema 驗證；agent 寫錯 → retry from agent stage
5. **demux**：Refuter / Forward / Backward / Counterexample / Generalizer / ConstructionSearch decision 進 queue（priority=high，左端 push）；Shelve 直接 UPDATE goals.status（不入 queue）
6. **blocked_pipelines 過濾**：Strategist 想 inject 對某 (Goal, pipeline kind) 但 blocked_pipelines 含該 kind → 跳過該 decision
6a. **decision payload model 覆寫**：Strategist decision 含 `{kind: 'Backward', target: 'G_x', model: 'opus'}` → 對應 inject 的 Backward 跑時實際用 opus 呼叫（驗 subprocess argv）
6b. **decision payload provider 覆寫 + reject 路徑**：步驟：(1) `asterism config set agent.providers '[claude]'`；(2) Strategist decision 含 `{kind: 'Backward', target: 'G_x', provider: 'gemini'}`；(3) 因 gemini 不在 `agent.providers` → reject decision + log warning + 不 inject
6c. **decision payload budget 覆寫**：Strategist decision 含 `{kind: 'ConstructionSearch', target: 'G_x', budget: {wall_clock_sec: 28800}}` → 對應 spawn 的 task `continuous_tasks.budget_wall_clock_sec=28800`（覆寫 framework 預設 14400）；驗 budget / range / mutation operators 三類 payload override 都 propagate

### Forward / Generalizer 行為

7. **Forward 從 negation seed 推**：人為 setup 一個 proved ¬G → Strategist 對該 negation inject Forward → agent 從 negation seed 提候選 corollary
8. **Generalizer 不自動 cascade**：人為 setup G proved + Generalizer 產 G* + G* proved → 原 G status / answer_data 不變（v3 §決策日誌段註明）
9. **dedupe (any) 過濾**：Forward / Generalizer 候選跟既有 Mathlib / Library / goals 撞 → discard、no_novel outcome（不算失敗）

### Multi-Problem Strategist

10. **Round-robin（嚴格輪詢）**：3 個 Problem 各注入 root 後跑 Strategist N 次（N≥9，每 Problem 至少觸發 3 次取樣）→ 各 Problem 觸發次數差 ±5%（容忍 cooldown timing 抖動，非 weighted 設計）。**機制驗法**：跑時觀察觸發順序符合 A→B→C→A→B→C 嚴格循環、無連續同 Problem
11. **Per-Problem 視野**：Strategist agent prompt 內 inventory 只含當次 Problem 的 metrics、不混其他 Problem

### Signal 接通驗證

「人為設置」一律走 `asterism fixture <name>` CLI（見 §引入元件 CLI 擴），對齊 P1 fault hook 風格、可重現：

12. **IH-trap 觸發**：`asterism fixture ih_trap` 注入預設狀態 → 跑 `asterism strategist run-once` → strategist_decisions 含 Refuter / Shelve action（取決於 prompt 設計）
13. **Silver 卡升級觸發**：`asterism fixture silver_stuck` → strategist run-once → decisions 含 inject 新 Refuter on G
14. **Construction plateau 觸發**：`asterism fixture construction_plateau` → strategist run-once → decisions 含 inject 新 ConstructionSearch with mutation operator override 或 Shelve
15. **blocked_pipelines 觸發**：`asterism fixture blocked_backward` → strategist run-once → decisions 含對 G 的非 Backward 救援 action（Refuter / Counterexample / Shelve）

### 整體 demo（pin 死數值由 spike-021 結果決定）

16. **D-baseline vs D-strategist 對照**：相同 5 root × 3 runs 取中位數。**spike-021 跑完後** 鎖定以下三選一作為 acceptance pin（在 spike-021 結果落 docs/spikes.md 同時更新本 acceptance 為具體數字）：
    - 路 1: wall-clock 中位數 ≤ 90% baseline
    - 路 2: token 中位數 ≤ 80% baseline
    - 路 3: 終態（proved/refuted/shelved）比例改進 ≥ 30%
    spike-021 跑完前 acceptance 鎖定 placeholder「待 pin」、phase 不得 ship；P7 開發者**不得**以「啟用後沒退步（改進 ≥ 0%）」就 ship——否則 phase value 等於零
17. **Generalizer demo**：手動 setup G1 / G2 結構相似（fixture）+ Strategist signal 觸發 → Generalizer 寫 G* → G* 入池 normal attack

## 依賴

### 前置 phase

- P1–P6 完成

### 必跑 spike

spike 編號接 P6 後（P6 已用至 spike-024；spike 編號集中由 `docs/spikes.md` 配發）：

- **spike-025 P7 baseline 量測**——對 P6 完成後跑 5 個 conjecture demo（混真假），量 wall-clock / token / 終態分布。為 P7 efficiency 對照建 baseline；**spike 完成後 pin 死 acceptance #16 數值**
- **spike-026 Strategist agent prompt 可行性**——餵 inventory metrics + decisions enum + signal hints 給 claude，看 agent 寫的 decisions 是否合理 + JSON schema valid。決定 prompt 模板複雜度
- **spike-027 Generalizer agent 寫 G\* 成功率**——準備 5 個已 proved Goal（Mathlib 內常見），跑 Generalizer agent，看 G* 通過 self_verify 比例
- **spike-028 Forward 從 negation seed 推**——準備 3 個 proved ¬G（P4 demo 跑出來的），跑 Forward agent，看是否能寫出有意義的 corollary
- **spike-029 Strategist model override 反饋值**——對 P3 demo D2 的 IH-trap Goal、跑兩組對照（一組 Strategist 用預設 opus、一組強制改 sonnet）→ Strategist decisions 品質 + downstream pipeline outcome 是否有差。決定 framework 預設 strategist=opus 是否值得

## 引入元件

### Pipeline

- **Forward**（pipelines.md §4）
- **Generalizer**（pipelines.md §8）
- **Strategist**（pipelines.md §5）

### DB schema（啟用 P1 預留）

- `strategist_decisions` table：P1 schema 已建、P7 起真實寫入
- `pipelines.kind`：'Forward' / 'Generalizer' / 'Strategist' enum value 啟用（P1 schema 已含）
- `events.kind`：考慮加 'strategist_run'（觀測用）；若加則 P1 schema 同步補 enum value

### Tooling 新增

- `Tooling/pipelines/forward.py`
- `Tooling/pipelines/generalizer.py`
- `Tooling/pipelines/strategist.py`
- `Tooling/strategist/inventory.py`：對齊 impl §6.4 SQL
- `Tooling/strategist/demux.py`：decision → queue inject / Shelve UPDATE，含 model/provider override 寫入 queue payload
- `Tooling/strategist/round_robin.py`：multi-Problem 輪詢
- 擴 `Tooling/agent/provider.py`：三層 model 解析的最高層（strategist payload）接通；P2 留 stub、P7 真實啟用
- 擴 `docs/prompts/`：`strategist.md`（含 model/provider override schema 解釋）、`forward.md`、`generalizer.md`
- 擴 `Tooling/cli.py`：`strategist run-once / decisions`、`inventory <problem>`

### Cascade table 擴行

- Goal shelved → cancel 同 Goal still-running 全部 pipeline
- Strategist decisions Shelve action → 直接 UPDATE goals.status='shelved'

### Config

| key | P7 預設 | runtime mutability |
|---|---|---|
| `K_strategist` | P×2（P=4 → K=8） | mutable |
| `M_strategist` | 5 | mutable |
| `strategist.enabled` | true（CLI flag 可關，demo 對照用） | mutable |
| `strategist.evidence_window` | 20（Strategist prompt 內看最近 N 個 evidence_updated event） | mutable |
| `strategist.decisions_lookback` | 10（過去 decisions outcome 反思進 prompt 的 N） | mutable |
| Forward / Generalizer retry 上限 | N_retry=10 | mutable |

## 任務序列

DB 端 P7 不需 schema migration（P1 已建全 schema）；spike 編號集中由 `docs/spikes.md` 配發。任務序列只列實作動作：

1. **spike-025 / 026 / 027 / 028 / 029 跑完**——結果落 `docs/spikes.md`；spike-025 結果出來後**鎖定 acceptance #16 pin 死數值**
2. **Inventory SQL**（`Tooling/strategist/inventory.py`）：對齊 impl §6.4
3. **Strategist agent prompt v1**（`docs/prompts/strategist.md`）：含 inventory + signals + decisions schema + decisions_lookback 反思段（SQL JOIN strategist_decisions × pipelines.outcome）
4. **Strategist pipeline runtime**（`Tooling/pipelines/strategist.py`）：completion stages + cooldown 控制
5. **Demux**（`Tooling/strategist/demux.py`）：decision → queue / UPDATE 分流 + blocked_pipelines 過濾 + payload override（model / provider / budget / range / mutation operators）propagate
6. **Multi-Problem round-robin**（`Tooling/strategist/round_robin.py`）：嚴格輪詢、`K_strategist` global 累計、cooldown 解除後切下個 Problem。**cooldown 是 global、non-overlapping**——同時間只一個 Strategist instance 在跑（per-Problem 並行 Strategist 是多實例設計、留 P8+；P7 不要誤實作 per-Problem cooldown）
7. **Forward pipeline runtime**（`Tooling/pipelines/forward.py`）：對齊 pipelines.md §4
8. **Forward agent prompt v1**（`docs/prompts/forward.md`）
9. **Generalizer pipeline runtime**（`Tooling/pipelines/generalizer.py`）：對齊 pipelines.md §8
10. **Generalizer agent prompt v1**（`docs/prompts/generalizer.md`）
11. **Cascade table 擴**：shelved 連鎖 cancel
12. **Reactor 補 step 5（Strategist 觸發判定）**（v3 §6 step 5；P3 留 `maybe_trigger_strategist()` no-op stub、P7 補實作）
13. **CLI 擴**：`config get/set/list`（含 mutability category 邏輯）、`strategist run-once / decisions / explain --last`、`inventory <problem>`、`fixture <name>`
14. **PR 架構文件補丁**（兩條同時送）：
    - v3 §6 cancellation 表加「shelved → cancel 同 Goal still-running 全部」trigger 行
    - architecture pipelines.md §5 加第 6 條 Strategist signal「Pipeline blocked_pipelines 觸發 → 強訊號需 meta 介入」
15. **D-baseline 跑（先把 strategist disable）+ 紀錄**
16. **D-strategist 跑（enable）+ 對照（依 spike-025 pin 的 acceptance #16 驗）**
17. **Generalizer demo**

**注意**：~~原草稿 task「移除 P4 silver-stuck hard rule」已刪除~~——P4 silver-stuck hard rule 改為**永久 mechanism**（不依 Strategist），確保 `strategist.enabled=false` 時 silver→gold 仍能自動完成。Strategist「Silver 卡升級」signal 是加碼（hard rule 已派過 Refuter 仍卡時派額外 Refuter）、不取代

## 測試

- **Unit**：Strategist agent 輸出 JSON schema 驗證
- **Unit**：Demux 對每 decision kind 正確 dispatch
- **Unit**：Inventory SQL 回傳結構正確
- **Unit**：Round-robin 多 Problem 公平性
- **Unit**：Cancellation 對 shelved 觸發
- **Integration**：Strategist signal 接通驗證（IH-trap / silver / plateau / blocked_pipelines / negation Forward 各 case）
- **Integration**：D-baseline vs D-strategist 對照
- **Integration**：Generalizer demo
- **Integration**：multi-Problem 並發 + Strategist round-robin

## 風險與 open questions

- **Strategist agent 可能 hallucinate decisions**：spike-026 結果若顯示 LLM 對 inventory metrics 的解讀不穩，inject 一堆無用 Refuter / Forward 燒 token。應變：M_strategist 限縮、加「過去 N 次 decisions outcome 反思」進 prompt——資料來源 SQL `SELECT d.decisions, p.outcome FROM strategist_decisions d JOIN pipelines p ON p.target_id IN (d.decisions targets) ORDER BY d.ts DESC LIMIT N`（**不是 dead_attempts**——Strategist 自身 outcome 才在 dead_attempts、要的是 downstream pipeline outcome）、寫進 Strategist agent prompt
- **Generalizer 沒自動 cascade 影響 demo 觀感**：G* proved 不升原 G、使用者可能誤以為「沒效果」。CLI `goal show` 要顯示「已 generalize 為 G*」這個橫向關係，雖然 status 不變
- **Forward 跟 Generalizer 都靠 Strategist inject 才動**：Strategist agent 若不夠主動，這兩 pipeline 永遠不跑、P7 等於沒上。**應變**：(a) spike-026 prompt 設計強調「探索 vs 收斂」平衡；(b) 若 spike 結果顯示 LLM 真不主動，加 hard rule 兜底：proved root 累計 N 次 / 系統 idle T 分鐘無 Generalizer / Forward 派出 → reactor 強制 inject 一次（rule 是 hardcoded、不靠 Strategist）；(c) `asterism strategist explain --last` CLI（P7 已落 §In）顯示 Strategist 不 inject 的理由，方便人類調 prompt
- **D-baseline vs D-strategist 量化困難**：5 個 root sample 太小，statistical noise 大。應變：跑多次取平均、demo 文件說明 statistical caveat、選 5 個 root 的成分要 cover 不同 case（IH-trap / silver / plateau / 攻不動）
- **Strategist round-robin 與 cooldown 互動已明寫於 §In**：global cooldown 解除後 round-robin 切下個 Problem、`K_strategist` global 累計（不分 Problem）；A → cooldown wait → B → cooldown wait → C 嚴格循環。若想要 per-Problem 並行 Strategist 變成多實例設計，留 P8+
- **`strategist.enabled=false` 的 fallback**：D-baseline 跑時 P3/P4/P5 算出來的 signals 沒人消費——以下兩條 hard rule 必須保留作為 disable 模式的安全網（**P7 上線後不能刪**）：
  - P3 「IH-trap 兜底自動寫 blocked_pipelines」
  - P4 「silver-stuck 自動 inject Refuter」（P4 本輪 review 已改為永久 mechanism）
  - 確保 `strategist.enabled=false` 環境（如 token cost 控制、production 簡化部署）silver→gold / IH-trap 自動處理仍能完成
- **Inventory SQL 在大圖效能**：spike-025 baseline 跑時順帶量；若 query > 5s，要加 index 或 materialized view
- **Cluster typed relation 缺**：Generalizer 真要發揮要 G ↔ G* 的 typed edge（auto-cascade）；P7 沒做、留 P8+。CLI 要明確標示
- **Token 成本爆炸**：P7 多三 pipeline + Strategist 高頻觸發，token 用量翻倍以上。應變：CLI 顯示每日 token spend、設 daily cap、超過自動 disable Strategist/Forward/Generalizer
- **Strategist 過度用 model override 燒錢**：agent 可能對每個 inject decision 都加 `model: 'opus'`，把 builder.tactic_llm 從 haiku 升到 opus、token 成本暴增 10×。應變：override 加 quota（每 Strategist run 最多 K 個 decision 帶 override）、prompt 內明示「override 是稀缺資源」
