# Phase 4 — Conjecture

## 目標

P1–P3 只能處理「使用者已知為真」的 theorem。P4 引入 conjecture 三線並攻：對 `kind=conjecture` Goal 同時派 Backward（試證）、Refuter（試反證）、Counterexample（找 witness），讓框架能對 unknown 命題作出 verdict。
**核心 mechanic**：silver→gold 升級——Counterexample 找到 witness 是 silver verdict、Refuter 後續證 ¬G 把 silver 升 gold；trust 強度只允許單向升級。
這 phase 把 `status` × `answer_data` enum 全打開、cancellation propagation 升級成 verdict-aware 白名單、引入 Evolution subsystem 的 atomic mode。

## Scope

### In

- **Goal kind dispatch**：structural refill 對 `kind=conjecture` Goal 並排 enqueue Backward + Refuter + Counterexample（v3 §6 task queue 段）
- **Refuter pipeline**（pipelines.md §3）：`failure_replay` → agent（寫 ¬G、若 G.evidence 含 witness 用 short proof template）→ self_verify → dedupe (local) → commit（INSERT ¬G + 雙向 twin_of UPDATE，begin_batch）
- **Counterexample pipeline**（pipelines.md §6，atomic 模式）：`failure_replay` → agent（寫 decidable predicate + domain + evaluator）→ self_verify → evaluate → commit（refuted_with_witness 或 evidence_only）
- **Evolution subsystem**（v3 §4.3、impl §7.2）：基礎介面 + atomic mode 實作；Counterexample atomic 是其退化 case（純枚舉，impl §7.3）
- **`tools/counterexample.lean`**（impl §8.1）：CLI evaluator subprocess
- **`status` × `answer_data` 全展開**（v3 §2.2）
  - `answer_data.type` 接 'classical' / 'witness' / 'conjectural'（'construction' 留 P5）
  - 配 SQL filter 用 `answer_data->>'type'` 慣例
- **Trust set kind=computational entry**（v3 §7.1、impl §5.3）
  - `trust_set` 含 `{name, kind:'computational', provenance, metadata: {evaluator_hash, range, seed}}`
  - Accept rule for `status='refuted', type='witness'` 啟用
- **Cancellation propagation 升級成 verdict-aware 正向白名單**（v3 §6 cancellation 段）
  - P2/P3 簡化版（cascade Goal proved 殺 target_id == G.id 的 pipeline）改成查白名單
  - **預設四條**（對齊架構 §6 cancellation 表，標清 verdict 來源 + cancel target 範圍）：
    1. **Goal G 本身 proved (full classical)**（Builder/Backward 鏈成功）→ cancel `target_id == G.id` 上 still-running 的全部 pipeline kind
    2. **Twin G refuted (full classical)**（Refuter→Builder 鏈成功）→ cancel `target_id == G.id` 上 全部 + cancel `target_id == ¬G.id` 上 全部（**雙 Goal 各自殺一次**，cascade 走 `twin_of` FK 找對家）
    3. **Counterexample silver (`type='witness'`)**（直接 silver verdict、無經 ¬G 路徑）→ cancel `target_id == G.id` 上 Builder / Backward / 其他 Counterexample；**Refuter 留**（升級用）
    4. **Strategy dead 連鎖**→ cancel `strategy_id == S.id` 上 still-running 的 Builder / Backward（**同 Strategy 範圍**，不是同 Goal——其他 Strategy 對該 Goal 仍可繼續）
- **Cascade dispatch action 結構支援 multi-target**：`CascadeAction` 帶顯式 `target_ids: list[id]` 參數（不是單一 target_id），覆蓋 twin propagation（如 #2 同時影響 G + ¬G）。P3 cascade dispatch 表 (cross-ref P3 §引入元件 §Reactor) 重構時就要預留此結構
- **Silver → Gold 升級 cascade**（v3 §6 cascade 段、impl §8.4）
  - cascade 處理 ¬G proved 時查 twin G 當前狀態：若 silver（refuted/witness）→ 升 gold（refuted/classical）+ trust_set 換 lean_axiom 集 + Library/Counterexamples/<G>.json 改寫
  - 升級不可逆（classical → witness 拒絕）
- **`evidence_update` stage**（v3 §3.5）兩件事拆開：
  - **(a) `goals.evidence` json column 寫入：P4 真實啟用**——Counterexample evidence_only 路徑 patch、Counterexample silver commit 也 patch witness（後續 Refuter 撈來用 short proof template，acceptance #4 直接驗）
  - **(b) `evidence_updated` event emit：P4 純 logging**——events table INSERT 寫入但無 reactor handler 消費；P7 Strategist 才有 consumer
  - 為 P5 ConstructionSearch checkpoint + P7 Strategist signal 鋪路
- **`events.kind: evidence_updated`** 啟用（P1 schema 預留 enum、P4 真實寫入）
- **silver-stuck 自動兜底 hard rule**（P4 引入、**永久 mechanism、不依 Strategist**）：structural refill 對 `status='refuted'` AND `answer_data.type='witness'` AND **無 active Refuter**（pipelines table 查 target_id == G.id AND kind='Refuter' AND status='running' = 0）的 Goal 自動 inject 一次 Refuter（一次性、不重複 inject）。**理由**：silver→gold 是核心 mechanic、Counterexample race 失敗 卡 silver 不該需 Strategist 才能救。**P7 Strategist「Silver 卡升級」signal 是加碼**（已有 active Refuter 但失敗時派額外 Refuter），不取代此 hard rule。**永久保留**——確保 `strategist.enabled=false` 環境（如 token cost 控制）silver→gold 仍能自動完成
- **Cascade fatal halt** 沿用 P1（v3 §6 step 3 失敗處理）
  - P1 已建 `fatal` event + scheduler halt 機制
  - P4 cascade rules 變多（silver/gold 升級 / twin / dual-proved），fatal 觸發點增加但機制不變
- **Counterexample `unproductive` 寫 blocked_pipelines**（pipelines.md §6 行為規則）
  - 跟 P3 通用機制（連 N 次失敗）獨立——unproductive 一次就寫，因為 unproductive = agent 判命題不可機械決定，不會因為再試而改變
- **Twin cascade 規則**（v3 §6 cascade 段）
  - ¬G proved → G refuted（按上面 silver/gold 分流）
  - G proved → twin ¬G refuted（cascade）
  - 雙 proved twin → fatal halt（dual-proved 不可能）
- **CLI 擴**：
  - `asterism goal add --kind conjecture` 支援
  - `asterism goal show <G>` 顯示 twin / cancel chain / silver-or-gold

### Out

- ConstructionSearch / continuous task runtime（P5）
- Forward / Generalizer
- Strategist（P7）——P4 內 Strategist signals 算出來但無消費者；不過 cancellation 白名單與 silver→gold 機制本身不靠 Strategist
- Library promotion（P6）——P4 寫 `Library/Counterexamples/<G>.json` 但**不**寫 Library/Theorems/proved.lean 也不寫 library_index（P6 才有）；json 是 Goal-level artifact，先寫沒問題
- Multi-Problem
- Counterexample continuous mode（架構保留欄位 `pipelines.runtime`，P4 只跑 atomic）
- Evolution subsystem 的 mutation operators 進階（P5 為 ConstructionSearch 才會有真實 mutation；P4 atomic Counterexample 退化為純枚舉）

## Demo

P pool=4（P2 預設）對 2 root × 3 線 = 6 atomic task 不夠 → demo 跑時 override `P=8`：

```bash
asterism config set P 8     # demo override；P4 framework 預設仍 P=4

asterism init --problem conj_demo

# 注入兩個 conjecture：一真一假
asterism goal add --problem conj_demo --slug true_conj --kind conjecture \
  --spec "∀ n : Nat, n ≥ 3 → n^2 ≥ 9"
asterism goal add --problem conj_demo --slug false_conj --kind conjecture \
  --spec "∀ n : Nat, n ≥ 2 → n^2 < 2*n"

asterism run
# 預期 true_conj：
#   三線並攻 → Counterexample 跑 Fin 1000 無 witness（evidence_only）
#                Backward 拆 → Builder 證 → cascade up → status=proved/classical
#                Refuter 寫 ¬G → Builder 試證 ¬G 失敗 → exhausted
#   最終 true_conj 跟著 Backward 鏈走到 proved/classical

# 預期 false_conj：
#   三線並攻 → Counterexample 1s 內找到 n=2 witness → silver verdict
#               commit refuted/witness + 寫 Library/Counterexamples json
#               cancellation：殺 Backward / 其他 Counterexample，Refuter 留
#   Refuter agent 跑時讀 G.evidence 撈到 witness、寫 short proof template
#   ¬G 入池 → Builder 證 ⟨2, by norm_num⟩ → proved
#   cascade twin → 升 gold：false_conj answer_data type 從 witness 改 classical
#   Library/Counterexamples json schema 改寫
```

## Acceptance criteria

0a. **Demo true_conj end-to-end**：上面 §Demo true_conj bash 跑完、最終 status='proved' + answer_data.type='classical'。**single sanity gate**
0b. **Demo false_conj end-to-end**：上面 §Demo false_conj bash 跑完、最終 status='refuted' + answer_data.type='classical'（silver→gold 升級鏈完成）。**single sanity gate**
1. **三線並排 enqueue**：對 `kind=conjecture` Goal 入池後 30s 內 atomic queue 出現 Backward + Refuter + Counterexample 三項
2. **Counterexample silver**：上面 false_conj demo，Counterexample 在 5 min wall-clock 內找到 witness、commit 寫 silver verdict、Library/Counterexamples 出現 type='witness' json
3. **Cancellation 白名單**：silver verdict 觸發後查 pipelines table，Backward / 其他 Counterexample 對該 Goal 已 SIGTERM、Refuter 仍 running
4. **Refuter witness 撈取**：Refuter agent prompt 內含 `evidence.counterexample_witness`（驗法：讀 `Staging/<p_uuid>/context.json` 的 `prompt` 欄位字串）
5. **Silver → Gold 升級**（三條 SQL 直接驗）：
   - `SELECT json_extract(answer_data, '$.type') FROM goals WHERE id=<G>` = `'classical'`
   - `SELECT json_extract(value, '$.kind') FROM goals, json_each(trust_set) WHERE goals.id=<G>` 全為 `'lean_axiom'`
   - `Library/Counterexamples/<problem>_<slug>.json` 內容 schema 含 `negation_lean_path` / `negation_goal_id`（type='classical' schema），不再含 `witness` / `evaluator_hash`（type='witness' schema）
5a. **silver-stuck stop-gap**：手動構造 false_conj race（Refuter 在 Counterexample commit 前完成 agent stage、寫一般 ¬G）→ Builder 證 ¬G fail → Goal 卡 silver；structural refill 偵測「silver/witness + 無 active Refuter」→ inject 新 Refuter → 帶 witness 證成功 → 升 gold。**驗證 demo false_conj 在無 Strategist 環境下仍能完成**
6. **單向升級（silently skip，不 fatal）**：用 `REFUTER_FAST_PATH=1` env hook 模擬 Refuter→Builder 鏈在 Counterexample 之前 commit ¬G → G 已 refuted/classical；隨後 Counterexample 也找到 witness、commit silver → cascade 偵測「target 已 classical」→ **silently skip UPDATE**、Counterexample pipeline outcome 改 `superseded`、寫 `events(silver_skipped_after_classical)` row、scheduler 不 halt（race 不是 invariant violation）
7a. **True conjecture（warm cache）**：CI 重複跑 true_conj demo，wall-clock < 15 min（Mathlib 已 build；含 Refuter 5 次 exhausted ~12 min + Backward 鏈成功）
7b. **True conjecture（cold cache）**：清 lake cache → wall-clock < 30 min（含首次 Mathlib build）
8. **Counterexample `unproductive` 寫 blocked**：人為注入 G 含實數量詞（agent 寫不出 decidable predicate）→ Counterexample agent 早退 unproductive、commit 寫 `goals.blocked_pipelines += ['Counterexample']`、後續 structural refill 跳過
9. **Cascade fatal halt（dual-proved invariant violation）**：用 `CASCADE_FAULT=dual_proved` env hook 模擬 G 與 ¬G 同時 proved（理論上不可能、是真正 invariant violation）→ scheduler emit `fatal` event + halt + 保留 working dir + DB 現場（沿用 P1 機制）。**注意 #6 race 路徑不走 fatal**——race 是預期行為、fatal 只給真正不可能的狀態
10. **Trust set computational entry 完整**：silver verdict 寫的 `trust_set` 含 evaluator_hash + range + seed metadata；缺任一 → accept rule reject

## 依賴

### 前置 phase

- P1 + P2 + P3 完成

### 必跑 spike

spike 編號接 P3 後（P3 已用至 spike-011）：

- **spike-012 Counterexample agent 寫 decidable predicate 成功率**——準備 10 個常見小命題（含真/假），跑 Counterexample agent，看 self_verify pass rate。決定 prompt 模板複雜度與 retry 預算
- **spike-013 Refuter witness-template 自動化**——驗證「給 witness `w`、要求 agent 寫 `theorem neg : ¬G := ⟨w, by ...⟩`」這個 prompt template 對不同命題形式的 robust 度
- **spike-014 cancellation propagation 對 lake 子程序**——SIGTERM 跑 lake build 的 subprocess 是否乾淨？是否 leak file handle？
- **spike-015 evaluator_hash composition**——silver verdict 的 `trust_set.metadata.evaluator_hash` 應含哪些 input 才足夠 reproducible？候選：(a) tool binary hash (`tools/counterexample.lean` sha256) (b) predicate file hash (c) domain expr 字串 hash (d) seed (e) Lean / Mathlib version。決定 hash composition formula；無共識則 silver verdict 後續無法重現

跨 phase spike 編號集中由 `docs/spikes.md` 配發（避免 phase 草稿期 collision）。

## 引入元件

### Pipeline

- **Refuter**（pipelines.md §3）
- **Counterexample**（atomic 模式，pipelines.md §6）

### Subsystem

- **Evolution**（v3 §4.3，atomic mode；Counterexample atomic 是其退化 case，impl §7.3）

### DB schema（啟用 P1 預留 enum）

P1 schema 已含全 enum value（codex review #12 決策）。**P4 不擴 schema**——只是開始消費：

- `pipelines.kind`：'Refuter' / 'Counterexample' enum value 啟用
- `pipelines.runtime`：'continuous' enum value 仍未消費（P5 才用）；P4 寫入的 row 全 `runtime='atomic'`
- `events.kind`：'evidence_updated' enum value 啟用；'fatal' P1 已啟用
- `goals.kind`：'conjecture' 啟用 dispatch（之前只跑 'theorem' 路徑）

### Tooling 新增

- `tools/counterexample.lean`（impl §8.1）
- `Tooling/pipelines/refuter.py`
- `Tooling/pipelines/counterexample.py`
- `Tooling/subsystems/evolution.py`（atomic mode；continuous 留 P5）
- `Tooling/cancellation.py`（白名單表 + SIGTERM 邏輯）

### Test infrastructure

新增 env hook（對齊 P1 `COMMIT_FAULT` 風格、總清單見 `docs/dev/test_hooks.md`）：

- `COUNTEREXAMPLE_FORCE`：mode ∈ `{silver, evidence_only, unproductive}`，給 acceptance #6 模擬 Counterexample 強制走特定 outcome
- `CASCADE_FAULT`：mode ∈ `{unique_violation, dual_proved, fk_invalid}`，給 acceptance #9 模擬 cascade SQL 失敗
- `REFUTER_FAST_PATH`：boolean，模擬 Refuter→Builder 鏈快速通過用於 race acceptance #6

### Cascade table 擴行

加 silver→gold 升級規則、twin cascade 雙向、Counterexample 兩 outcome 分流、cascade fatal halt 處理。

### Config

| key | P4 預設 |
|---|---|
| `counterexample_atomic_budget` | 5 min |
| `counterexample_atomic_range_default` | 1000 |
| Refuter retry 上限 | N_retry=10 |
| cancellation SIGTERM grace | 5s（之後 SIGKILL） |

## 任務序列

DB 端 P4 不需 schema migration（P1 已建全 enum）；任務序列只列實作動作：

1. **spike-012 / 013 / 014 / 015 跑完**——結果落 `docs/spikes.md`
2. **`tools/counterexample.lean`**：對齊 impl §8.1 介面（含 spike-015 決定的 evaluator_hash composition）
3. **`evidence_update` stage**（`Tooling/stages/evidence_update.py`）：goals.evidence column patch + emit `evidence_updated` event。**順序 prerequisite**：在 Counterexample pipeline 之前建好（後者 evidence_only 路徑要呼叫）
4. **Evolution subsystem 基礎**（`Tooling/subsystems/evolution.py`）：介面對齊 impl §7.2，先實作 atomic mode loop
5. **Counterexample pipeline runtime**（`Tooling/pipelines/counterexample.py`）：呼 evolution.run + commit (silver) / evidence_update (evidence_only)
6. **Refuter pipeline runtime**（`Tooling/pipelines/refuter.py`）：agent + self_verify + dedupe + commit batch (twin_of 雙向)
7. **Refuter agent prompt v1**（`docs/prompts/refuter.md`）：含 G.evidence 傳遞 + witness-based template instruction
8. **Counterexample agent prompt v1**（`docs/prompts/counterexample.md`）：含 evaluator code Lean 範例（predicate 是 Lean `def`）
9. **Cascade table 擴行 + silver→gold 升級邏輯**（`Tooling/cascade.py`）：
    - Counterexample silver verdict（直接 G refuted/witness）
    - Refuter→Builder ¬G proved + twin cascade（含 silver→gold 升級檢查）
    - Goal proved → twin ¬G refuted
    - 降級嘗試（silver 試圖覆寫 classical）→ silently skip + emit events row + outcome=`superseded`（**不 fatal**）
    - dual-proved twin → fatal halt（真正 invariant violation）
10. **Cancellation 白名單**（`Tooling/cancellation.py`）：實作 §In 列的 4 條白名單（取代 P2/P3 的簡化殺全部）：
    - 條 1：Goal G proved (full classical) → cancel `target_id == G.id` 全部
    - 條 2：Twin G refuted (full classical) → cancel G.id + ¬G.id 各自全部（cascade 走 twin_of FK）
    - 條 3：Counterexample silver → cancel G.id 上 Builder/Backward/其他 Counterexample；Refuter 留
    - 條 4：Strategy dead → cancel `strategy_id == S.id` 同 Strategy 範圍 Builder/Backward
11. **structural refill 加 kind=conjecture dispatch**（reactor 內）
12. **structural refill 加 P4 silver-stuck stop-gap hard rule**：對 status='refuted' AND answer_data.type='witness' AND 無 active Refuter 的 Goal 自動 inject 一次 Refuter（一次性）。**P7 移除**——P7 任務序列已含對應 task
13. **Cascade fatal halt 觸發點擴展**（沿用 P1 機制）：cascade table 內 dual-proved + 其他真正 invariant violation 觸發 emit fatal + halt；race / 降級 silently skip 不算
14. **CLI 擴**：`--kind conjecture`、`asterism goal show` 顯示 twin / silver-or-gold
15. **Test hooks**：`COUNTEREXAMPLE_FORCE` / `CASCADE_FAULT` / `REFUTER_FAST_PATH` env hook（test-only）
16. **Demo true_conj / false_conj 跑通 + acceptance test**

## 測試

- **Unit**：Cascade table 對 silver / gold / dual-proved / classical→witness reject 各 case
- **Unit**：Cancellation 白名單對四條 verdict trigger 正確 cancel set
- **Unit**：Counterexample evaluator 對找到 / 找不到 / timeout 各 case
- **Unit**：Refuter witness-template 對 evidence 含 witness / 不含 witness 兩 case
- **Integration**：false_conj demo 完整 silver → gold 鏈
- **Integration**：true_conj demo Backward 鏈 + Counterexample evidence_only
- **Integration**：unproductive 自動寫 blocked_pipelines
- **Integration**：cascade fatal halt + 重啟 recovery——`CASCADE_FAULT=dual_proved` 觸發 → halt → unset env → restart scheduler → assert cascade 完成、Goal 進終態（pytest 自動化、不需人類介入）
- **Stress**：10 個 conjecture root 並發，測 cancellation 是否乾淨

## 風險與 open questions

- **Counterexample agent 寫 decidable predicate 易出 bug**：spike-011 結果可能顯示 retry 預算需拉高、或 prompt 要附 example。也可能某些命題 agent 永遠寫不對 → 走 unproductive + blocked
- **Refuter race condition 由 §In silver-stuck 自動兜底 hard rule 處理**——P4 引入、永久保留；P7 Strategist「Silver 卡升級」signal 是加碼（hard rule 已失效時派額外 Refuter），不取代
- **trust_set 內 computational entry 的 evaluator_hash 怎麼算**：對 `tools/counterexample.lean` 本身做 sha256？還是要含 predicate file 的 hash？影響 reproducibility 重現性。spike-011 順帶決定
- **silver verdict 寫 Library json 但 P6 才有 library_index**：P4 寫 json 但不 INSERT library_index row（沒 table）→ P6 上線時要回掃既有 json 補 INSERT。應變：P6 寫個 `asterism library reindex` migration tool
- **cancellation SIGTERM 對 evolution subprocess**：spike-013 結果若顯示 Lean subprocess SIGTERM 後不乾淨，需加 fallback SIGKILL + 5s grace
- **Counterexample atomic 5 min budget 對某些命題太短**：domain Fin 1000 可能 1 秒跑完，domain 大時 5 min 不夠。spike-011 順便評估；P5 升 continuous 才能徹底解
- **三線並攻吃 P pool + true_conj Refuter 必失敗拖延**：3 個 root × 3 線 = 9 task，P pool=4 會排隊；demo 已 override `P=8`（§Demo 起手 `asterism config set P 8`）。**true_conj 的 Refuter 必失敗**（¬(∀n≥3, n²≥9) = 假）→ 跑滿 N=5 次 exhausted 才被 blocked、每次 ~3 min（含 Backward 嘗試證 ¬G 拆）= ~15 min 純 Refuter 拖延；30 min budget 對 cold cache 緊張、warm cache OK（acceptance #7a/#7b 已拆）。P7 Strategist 智慧優先級可砍 Refuter 早死
