# Pipeline 細節（v3 配對文件）

對應 `architecture_v3.md` §5。本文列八個 pipeline 各自的 **速查（觸發來源 / Runtime / Pool / 預設 model / cancellation 行為）+ stage 序列 + outcome + 行為規則**。共用部分（Runtime 規則、commit 協議、Session 策略）留在 v3 §5。

**Pipeline 觸發來源全表**（v3 §6 task queue 段）：

| Pipeline | structural refill | Strategist inject | Pool |
|---|---|---|---|
| Builder | ✅（leaf Strategy） | ❌ | atomic |
| Backward | ✅（多數）| ✅（高優先案例） | atomic |
| Refuter | ✅（kind=conjecture 三線並攻 + silver-stuck stop-gap） | ✅（theorem-kind 唯一通道 / silver 卡升級加碼） | atomic |
| Counterexample | ✅（kind=conjecture 三線並攻） | ✅（加碼 / theorem-kind sanity check） | atomic |
| ConstructionSearch | ✅（kind=construction） | ✅（加碼 budget / 換 mutation） | continuous |
| **Forward** | ❌ | ✅（**唯一來源**） | atomic |
| **Generalizer** | ❌ | ✅（**唯一來源**） | atomic |
| Strategist | event count 觸發（K_strategist=P×2）| — | atomic |

**設計原則**：有 structural refill 觸發的 pipeline 派發規則是**結構性的**（leaf Strategy / open Goal / kind dispatch）；只能 Strategist inject 的（Forward / Generalizer / Refuter on theorem-kind）派發**沒明確結構規則**、需 LLM 看 inventory 才該派——避免結構性 BFS 撈所有 proved Goal 都派 Forward 燒 token。

**Cancellation 白名單**（v3 §6 cancellation 表，正向白名單；新加 pipeline 預設不入名單）：

| Verdict 觸發源 | 該 cancel 的 still-running pipeline kinds |
|---|---|
| Builder/Backward 鏈 → Goal proved (full classical) | Builder, Backward, Refuter, Counterexample, ConstructionSearch（target=G.id） |
| Refuter→Builder 鏈 → twin G refuted (full classical) | 同上（target 跨 G.id + ¬G.id 雙 Goal 各殺一次） |
| Counterexample silver (`type='witness'`) | Builder, Backward, 其他 Counterexample（**Refuter 留**——升級用） |
| ConstructionSearch silver (`type='construction'`) | Backward, 其他 ConstructionSearch（**Builder 留**——升級用） |
| Strategy dead 連鎖 | Builder, Backward 對應 Strategy 的 still-running |
| Goal shelved（Strategist Shelve action）| 同 Goal still-running 全部 pipeline kind |

---

## 1. Builder

攻一個葉子 Strategy（無 sub-Goal 的 Strategy）。

**速查**：

| 維度 | 值 |
|---|---|
| 觸發來源 | structural refill：BFS 撈到「全 sub-Goal proved 的 Strategy」自動 enqueue |
| Runtime / Pool | atomic / P（atomic pool） |
| 預設 model | `agent.model_defaults.builder.tactic_llm: haiku`（低 cost、tactic 試多次） |
| 被 cancel 時機 | Goal proved (full classical) / Goal refuted (full classical) / Strategy dead；Counterexample silver / ConstructionSearch silver 也會 cancel（後者 silver 對輔助 Goal 的 Builder 例外不 cancel） |
| 對外 cancel | 無（Builder 自身不主動 cancel 別的 pipeline） |

Stages：

```
1. tactic_try        (pure)   常見 tactic 暴力試
                              [pass → success]
2. failure_replay    (pure)   讀 dead_attempts（target=該 Strategy）
3. find_lemmas       (pure)   找候選 lemma
4. tactic_llm        (agent)  三擇一輸出：
                              a) 寫 tactic proof → 進 step 5
                              b) 早退 needs_decomposition
                              c) 早退 bad_goal
5. self_verify       (pure)   驗單檔
                              [pass → proved]
                              [fail → retry from step 4]
6. commit            (pure)   mv staging .lean 到 Strategy 正式位置 + UPDATE strategies.status
```

Outcome：

```
proved          — self_verify pass
exhausted       — self_verify retry 用盡
needs_decomp    — agent 早退（必須進一步拆解）
bad_goal        — agent 早退（缺條件 / 看似為假）
```

`bad_goal` 反應：

- INSERT dead_attempts（target=該 sub-Goal、reason=「Builder reviewed bad: ...」）
- INSERT dead_attempts（target=父 Goal、reason=「prior decomp produced bad sub-Goal <G_id>: ...」）——確保父 Goal 下個 Backward 在 failure_replay 撈得到此教訓
- cascade 殺掉產生此 sub-Goal 的上游 Strategy。其他 sub-Goal 仍獨立留在 goals table，proved 狀態不丟，可被新 Strategy 透過 find_subgoals 重用
- 框架對父 Goal 派新 Backward

---

## 2. Backward

拆一個 Goal，產出新 prove-Strategy + sub-Goal。

**速查**：

| 維度 | 值 |
|---|---|
| 觸發來源 | structural refill（多數）：BFS 撈到 `status='open'` 的 Goal 自動 enqueue<br>Strategist inject（少數）：高優先案例（如 IH-trap signal 後 Strategist 判該換角度再拆） |
| Runtime / Pool | atomic / P（atomic pool） |
| 預設 model | `agent.model_defaults.backward.agent: sonnet`（拆解需語意理解、比 tactic 試貴） |
| 被 cancel 時機 | Goal proved (full classical) / Goal refuted (full classical) / Strategy dead（同 strategy_id 範圍）；Counterexample silver 也會 cancel |
| 對外 cancel | 無 |
| `unproductive` outcome | 寫 dead_attempts；P3 通用 N=5 機制累計後寫 `goals.blocked_pipelines += ['Backward']`；IH-trap special-case 連 ≥ 2 次 unproductive AND `parent_subgoal_max_similarity ≥ 閾值` → 立即寫入（不等 N=5，v3 §7.5） |

Stages：

```
1. failure_replay    (pure)   讀 dead_attempts（target=該 Goal）
2. find_lemmas       (pure)   找候選 lemma
3. find_subgoals     (pure)   列現有孤兒 Goal（Backward-only search 包裝），鼓勵 claim
                              既有而非重新拆出語意重複的 sub-Goal
4. agent             (agent)  生 PROPOSAL：combinator + 新 sub-Goal + claim 候選
5. dedupe (local)    (pure)   每個新 sub-Goal vs goals table 全 dedupe
                              hit → 改 combinator reference 到既有 Goal、跳過建檔
                              miss → 保留為新 sub-Goal
6. validator         (pure)   hypothesis carry / slug collision / sub-Goal 數量
                              （hypothesis carry 走 Lean meta；禁 regex parse Lean 源碼，
                               詳 v3 §7.4）
                              [fail → retry from step 4]
7. self_verify (multi)(pure)  驗多檔協同
                              [pass → success]
                              [fail → retry from step 4]
8. commit            (pure)   INSERT goals (新 sub-Goals) + INSERT strategies + INSERT strategy_subgoals
                              + mv staging .lean 到正式位置
                              + 對每個新 sub-Goal 算 similarity vs 父 Goal，存進
                                strategies.parent_subgoal_max_similarity（給 Strategist
                                偵測 IH-trap，v3 §7.5）
```

Outcome：

```
success
exhausted       — retry 用盡
unproductive    — agent 早退（判這 Goal 拆不動）
```

---

## 3. Refuter

建立 ¬G 為新樹根、與 G 互設 twin_of。¬G 從此是普通 Goal，由 Builder/Backward 攻擊；證了 ¬G 觸發 cascade，G 標 refuted（若 G 已 silver-refuted 則升級為 RefutedClassical）。

**速查**：

| 維度 | 值 |
|---|---|
| 觸發來源 | **三條來源**：<br>(1) structural refill（kind=conjecture 三線並攻：Backward + Refuter + Counterexample 同時派）<br>(2) structural refill **silver-stuck stop-gap hard rule**：`status='refuted' AND answer_data.type='witness' AND 無 active Refuter` → 自動 inject 一次（解 Counterexample/Refuter race condition；**永久 mechanism、Strategist disable 時也跑**）<br>(3) Strategist inject：對 theorem-kind Goal 派**只能**走 Strategist（無結構性觸發）；對 conjecture-kind 加碼派額外 Refuter（如「silver 卡升級」signal hard rule 已派但仍卡時）|
| Runtime / Pool | atomic / P（atomic pool） |
| 預設 model | 未明定（agent stage 跑 ¬G statement + witness-based template）；建議走 sonnet 級 |
| 被 cancel 時機 | Goal proved (full classical) / twin G refuted (full classical)；**Counterexample silver 時不被 cancel**（保留升級用） |
| 對外 cancel | 無（Refuter 證 ¬G 成功的 cancellation 由 cascade 套白名單） |
| `unproductive` outcome | 寫 dead_attempts；P3 通用 N=5 機制累計 |

Stages：

```
1. failure_replay   (pure)   讀 dead_attempts（target=該 Goal，含 refute 失敗）
2. agent            (agent)  寫 ¬G 的 Lean statement。
                             **若 G.evidence 含 counterexample witness `w`** →
                                  優先用 witness-based template 寫
                                  `theorem neg_g : ¬G := ⟨w, by decide⟩`（或同類短路徑）
                             無 witness → 寫一般 ¬G statement
3. self_verify      (pure)   驗 ¬G statement type-checks
                             [fail → retry from step 2]
4. dedupe (local)   (pure)   查 goals table 是否已有 α-equivalent ¬G
5. commit           (pure)   - novel：INSERT goals (¬G, origin='refuter_negation', kind='theorem',
                                                     depth=0)
                                       + mv staging .lean
                                       + UPDATE 雙向 twin_of
                             - dup：UPDATE 雙向 twin_of 指既有 ¬G（不建新 Goal）
```

Outcome：

```
success         — ¬G 入池為新樹根
exhausted       — retry 用盡（agent 寫不出有效 ¬G statement）
```

¬G 之後走 normal Backward / Builder 鏈；證成功時 cascade（v3 §6）會把 G 翻為 RefutedClassical（若 G 原 RefutedWitness，trust 強度升級 silver → gold）。

---

## 4. Forward

從已證 Goal 推新 Goal 入 Goals/（孤兒，origin=forward）。

**速查**：

| 維度 | 值 |
|---|---|
| 觸發來源 | **Strategist inject only**——架構唯二「無 structural refill 自動派」之一（另一是 Generalizer）<br>**理由**：對哪個 proved Goal 該推 corollary 沒明確結構規則；BFS 撈所有 proved 都派 Forward 會炸 token、需 LLM judgment<br>**Contingency hard rule**（spike-026 結果若顯示 LLM 不主動）：proved root 累計 N 次 / idle T 分鐘無 Forward 派出 → reactor 強制 inject 一次（hardcoded、不靠 Strategist）。**P7 default 不開**、視 spike 結果決定 |
| Runtime / Pool | atomic / P（atomic pool） |
| 預設 model | 未明定（agent stage 從 seed 提 corollary 候選）；建議走 sonnet 級 |
| 被 cancel 時機 | 無（Forward 跑時不依附特定 Goal terminal verdict） |
| 對外 cancel | 無 |
| `no_novel` outcome | dup → discard、不算失敗、不寫 dead_attempts |

Stages：

```
1. failure_replay    (pure)   讀 dead_attempts（target_kind=forward）
2. find_pattern      (pure)   本地所有 `status='proved'` 的 Goal 為推導種子，**不分 origin**——
                              含 root / backward / forward / refuter_negation。
                              negation 形式的 proved Goal（¬G）一視同仁，
                              agent 可從 negation seed 推 corollary（如 ¬G ⟹ ¬H_i）
3. find_mathlib      (pure)   列 Mathlib 內相關條目，避免 agent propose 已有
                              （Forward-only search 包裝）
4. agent             (agent)  根據 seed + 既有清單提候選 Goal
5. self_verify       (pure)   驗候選 statement type-checks
                              [fail → retry from step 4]
6. dedupe (any)      (pure)   候選 vs Mathlib + Library + goals table 全去重
                              dup → discard（不算失敗）
7. commit            (pure)   novel → INSERT goals (origin=forward) + mv staging .lean
```

Outcome：

```
success         — 至少一個 novel Goal 入池
no_novel        — 全 dup
exhausted       — agent 想不出候選
```

Forward 跟 Generalizer 都產新 Goal 入池，差別：Forward 推**下游 corollary**（如 G ⟹ H）、Generalizer 推**上游抽象**（找包含 G 的更廣命題 G\*）。兩者 Strategist signal 與 prompt 設計不同。

---

## 5. Strategist

Meta-coordinator。週期性看 Graph 全景，決定要派哪些 fuzzy-trigger pipeline（Refuter / Forward / 高優先 Backward）跟 shelve 哪些 Goal。輸出注入 task queue 左端。

**速查**：

| 維度 | 值 |
|---|---|
| 觸發來源 | event count 累計：每 `K_strategist` 個 `pipeline_finished` event 達標（預設 P×2，P=4 → K=8）+ cooldown 釋放 → 自動 inject Strategist task<br>multi-Problem 時走嚴格 round-robin（K_strategist global 累計、cooldown 解除後切下個 Problem，cooldown global non-overlapping） |
| Runtime / Pool | atomic / P（atomic pool）|
| 預設 model | opus（spike-029 決定值不值；多數 inventory 推理 + decision schema 寫作，需強 reasoning） |
| 被 cancel 時機 | 無（Strategist 自身跑時不被打斷） |
| 對外 cancel | 透過 `Shelve` decision 觸發 cascade（Goal shelved → cancel 同 Goal still-running 全部 pipeline，v3 §6 cancellation 表第 6 條） |
| Cooldown | Strategist 自身跑時不重派；commit 完才釋放 cooldown 旗標 |
| Inject 上限 | 單次 ≤ `M_strategist=5` 個 task |
| Decision payload override | `{model?, provider?, budget?, range?, mutation_operators?}`——架構 §8.3 三層 model 解析的最高優先層；對 stuck Goal 加強用 opus、或 ConstructionSearch 加 budget |

Stages：

```
1. failure_replay    (pure)   讀 dead_attempts（target_kind=strategist，自身過去決策 vs 結果）
2. inventory         (pure)   Strategist-only metrics view，無 cap。聚合維度：
                              per Goal：status / depth / status_changed_at / bad_goal_count /
                                        attempting_age / child_strategy_outcomes
                              per subtree：depth 分布 / Strategy unproductive ratio
                              全域 top-N：最多 bad_goal / attempting 最久
                              （具體 SQL 見 impl §6.4）
3. agent             (agent)  輸出 decisions list
4. self_verify       (pure)   檢查 JSON schema 正確
                              [fail → retry from step 3]
5. commit            (pure)   INSERT strategist_decisions row，scheduler 注入 queue
```

decisions schema：

```json
[
  { "kind": "Refuter",  "target": "G0014" },
  { "kind": "Forward",  "count": 3 },
  { "kind": "Backward", "target": "G0042" },
  { "kind": "Shelve",   "target": "G0007" }
]
```

Outcome：

```
success         — decisions 寫入完成
exhausted       — agent 寫不出有效 schema
```

**Strategist 行為規則**

- **Shelving**：Strategist 主動列 Shelve action。框架不額外加 fallback——若 Strategist 失職該 Goal 留 attempting，由 control_signal pause + 人類 review 處理
- **自我修正**：Strategist agent 透過 step 1 failure_replay 看自己過去決策的後續結果，反思並調整方向
- **M 約束**：每次 inject ≤ M_strategist 個 task，agent 從候選決策中挑 top priority
- **Decision signals**（agent prompt 內建）：
  - Goal 有多次 Builder bad_goal → 強訊號該派 Refuter
  - Goal attempting 過久無 cascade → 弱訊號可能該 Refuter / Shelve
  - Strategy 都 unproductive → 弱訊號 Refuter
  - 分支 depth 劇增且未接觸 Mathlib lemma → 建議 Shelve（防失控遞迴）
  - **IH-trap**：Strategy 連 ≥ 2 次 unproductive AND `parent_subgoal_max_similarity ≥ 閾值` → 強訊號 Refuter / Shelve（v3 §7.5）
  - **新形式化的 negation**：cascade 剛把某 Goal 翻成 `status='refuted'` 且 `answer_data.type='classical'`（透過 Refuter 證 ¬G 成功）→ 弱訊號可考慮 inject Forward on 該 negation Goal，找下游 corollary（如 ¬G ⟹ ¬H_i）
  - **Silver 卡升級**：G `status='refuted'` 且 `answer_data.type='witness'` AND `evidence` 含 counterexample witness AND 對 G 無 active Refuter（race condition：Refuter 早於 Counterexample 跑完 agent stage 時用了一般 ¬G template，沒撈到 witness）→ 弱訊號 inject 新 Refuter on G（會撈 witness 用 short proof template 重試 silver → gold 升級）
  - **Construction score plateau**：active ConstructionSearch task 連續 ≥ 20 代無 best_score 改進 → 弱訊號 inject 新 ConstructionSearch with mutation operator override，或 Shelve
  - **Construction 接近 target**：active ConstructionSearch best_score ≥ target × 0.95 → 強訊號加碼 budget（continuous → 延長 wall-clock）衝最後一哩
  - **Pipeline 自動 blocked**：某 Goal 的某 pipeline kind 連 N 次失敗被自動寫進 `blocked_pipelines`（v3 §9.1）→ 強訊號需要 meta 介入；Strategist 評估是否 Shelve 整個 Goal、或換角度（如改派 Refuter / Counterexample）

  具體 prompt 設計留實作階段

---

## 6. Counterexample（atomic 模式）

對 `kind=conjecture` Goal 找反例 witness。產出 silver verdict（`RefutedWitness`、trust kind=computational）；後續 Refuter 證 ¬G 成功時 cascade 自動 silver → gold 升級（見 v3 §6）。

目前只支援 atomic 模式（單次跑 budget 內），continuous 模式延後。

**速查**：

| 維度 | 值 |
|---|---|
| 觸發來源 | structural refill（kind=conjecture 三線並攻：跟 Backward + Refuter 並排）<br>Strategist inject（加碼：domain 不夠時換更大 range；對 theorem-kind sanity check） |
| Runtime / Pool | atomic / P（atomic pool）；continuous 模式延後（Pool=continuous 時用 P_continuous） |
| 預設 model | 未明定（agent stage 寫 decidable predicate + evaluator code）；建議走 sonnet 級 |
| 被 cancel 時機 | Goal proved (full classical) / Goal refuted (full classical)；Counterexample silver 也會 cancel **其他** Counterexample（同 G） |
| 對外 cancel | silver verdict 後 cancel G.id 上 Builder / Backward / 其他 Counterexample；**Refuter 留**（保留 silver→gold 升級用） |
| `unproductive` outcome | **一次就寫** `goals.blocked_pipelines += ['Counterexample']`（跟 P3 通用 N=5 機制獨立——unproductive = agent 判命題不可機械決定，不會因再試而改變） |
| `evidence_only` outcome | 不算失敗、不寫 blocked、可被 Strategist 加碼派 |

Stages：

```
1. failure_replay     (pure)   讀 dead_attempts（target=該 Goal）
2. agent              (agent)  寫 decidable predicate + 列舉 domain（如 Fin 1000）+ evaluator code
                               早退 outcome=unproductive：agent 判 predicate 不可 decide
3. self_verify        (pure)   驗 predicate 與 evaluator 的 Lean 表達 type-checks
                               [fail → retry from step 2]
4. evaluate           (pure)   在 domain 內跑 evaluator
                               找到反例 witness w → 帶 w 進 step 5
                               至 K（budget 用盡或 domain 跑完）無反例 → 帶 (K, evidence) 進 step 5
5. commit             (pure)   - 反例 case：UPDATE G status='refuted',
                                            answer_data={type:'witness', witness, evaluator_hash, range, seed},
                                            trust_set=[<computational entry>]
                                            + 寫 Library/Counterexamples/<problem>_<slug>.json
                                            + UPDATE G.evidence patch witness（給後續 Refuter
                                              用 witness-based template，見 §3 Refuter）
                                            + cancel G 還在跑的 Builder / Backward / 其他
                                              Counterexample（**Refuter 不 cancel**——讓它有
                                              機會升級 silver → gold）
                               - evidence-only：evidence_update（§3.5）合 patch
                                            {counterexample_tested_up_to: K}
                                            + emit `evidence_updated` event
```

Outcome：

```
refuted_with_witness    — 找到反例，G 直接 silver verdict
evidence_only           — 至 K 無反例
unproductive            — agent 早退（predicate 不可 decide）
exhausted               — self_verify retry 用盡
```

Outcome 分類：前兩屬 success class；後兩屬 failure class。

**行為規則**

- **Budget**：atomic 單次 wall-clock ≤ `counterexample_atomic_budget`（預設 5 min），domain 上限 `counterexample_atomic_range_default`（預設 1000）。兩者見 v3 §8 配置
- **Trust set**：refuted_with_witness 的 Goal `trust_set` 含 `kind=computational` entry，其 `provenance` 含 evaluator hash + range + seed（reproducibility 必要）
- **Cancellation**：找到反例後 cancel G 還在跑的 Builder / Backward / 其他 Counterexample；**Refuter 不 cancel**（保留 silver → gold 升級機會）
- **重派條件**：unproductive 後 commit 寫 `goals.blocked_pipelines += ['Counterexample']`，structural refill 與 Strategist inject 都會跳過該 Goal 的 Counterexample；evidence_only 不算失敗、不寫 blocked，可被 Strategist 加碼（continuous 模式留待後續 Pack）
- **共用 Evolution subsystem**：底層搜尋 / scoring / reproducibility metadata 走 v3 §4.3 Evolution subsystem（atomic 模式內 evolution loop 退化為純枚舉，介面對齊 ConstructionSearch）

---

## 7. ConstructionSearch（continuous 模式）

對 `kind=construction` Goal 找滿足 spec 的 instance witness。產出 silver verdict（`status='proved'` AND `answer_data.type='construction'`，trust kind=computational）；後續 Builder 證 `∃X, P(X)` 成功時 cascade 自動 silver → gold 升級（見 v3 §6）。

走 continuous task runtime（v3 §5）：長運行（hours-days）、定期 checkpoint、可 pause/resume。

**速查**：

| 維度 | 值 |
|---|---|
| 觸發來源 | structural refill（kind=construction：跟 Backward 並排；Builder 不直接派、由 Backward 後續產 Strategy 才走 leaf 規則）<br>Strategist inject（加碼 budget / 換 mutation operator override / score plateau 救援）|
| Runtime / Pool | **continuous** / P_continuous（background pool，預設 P/4）|
| 預設 model | `agent.model_defaults.construction_search.generate: haiku`（每代 N 候選、高頻呼叫、低 cost 必要） |
| Lifecycle | `running / paused / done / killed`（continuous_tasks 表）；可 pause / resume；`T_pause_max=7 days` 自動 killed |
| Crash recovery | scheduler 啟動掃 `lifecycle_state='running'` task：checkpoint_state 完整 → resume；殘缺（含 checkpoint_state=NULL「首檔 checkpoint 前 crash」case）→ killed + alert，**不 auto-resume from 0**（impl §9.3） |
| 被 cancel 時機 | Goal proved (full classical) / Goal refuted (full classical)；ConstructionSearch silver 也會 cancel **其他** ConstructionSearch（同 G）|
| 對外 cancel | silver verdict 後 cancel G.id 上 Backward / 其他 ConstructionSearch；**Builder 留**（保留升級用——輔助 Goal 的對應 Builder） |
| Cancellation 機制 | SIGTERM + 5s grace → SIGKILL（impl §9.3） |
| `unproductive` outcome | 寫 dead_attempts；P3 通用 N=5 機制累計 |

Stages：

```
1. failure_replay     (pure)   讀 dead_attempts（target=該 Goal）含過去代失敗摘要
                              （只在 task 啟動時跑一次，後續 loop 不重跑）
2. generate           (agent)  依 mutation operator + 上代 best 產 N 個候選 candidate
                               first generation 由 random / heuristic seed
3. compile            (pure)   各候選寫 staging .lean、跑 `lake env lean` type-check
                               type-fail → 該候選 discard
4. evaluate           (pure)   通過 type-check 的候選跑 scorer（spec 自帶的 Python module）
                               每候選得分 score
5. select             (pure)   保留 top-K（K 由 mutation operator 決定）
6. checkpoint         (pure)   寫 construction_attempts table 該代每候選一行
                               UPDATE continuous_tasks.checkpoint_state
                               若 best_score 改進 → evidence_update + Library/Constructions/<G>.json
                                 同檔覆寫（type='construction' schema）
                               emit `task_checkpoint` event
7. commit             (pure)   - score ≥ target case：UPDATE G status='proved',
                                            answer_data={type:'construction', witness_lean_path,
                                                         score, evaluator_hash, generation, seed},
                                            trust_set=[<computational entry>]
                                            + 寫 Library/Constructions/<G>.json
                                            + spawn 輔助 Goal `∃ X, P(X)` (origin='construction_witness',
                                              kind='theorem', derived_from=G)，帶現成 Strategy proof
                                              body 候選 `⟨witness, by decide⟩` 等入池
                                            + UPDATE G.evidence patch witness（給輔助 Builder 用）
                                            + cancel G 還在跑的 Builder / Backward / 其他 ConstructionSearch
                                              （**輔助 Builder 不 cancel**——保留 silver → gold 升級機會）
                               - evidence_only case：evidence_update（§3.5）合 patch
                                            {best_known: {witness, score, generation},
                                             generations_completed: N}
                                            + emit `evidence_updated` event
```

**Loop 控制**（不是獨立 stage、是 step 6 後的分支）：

每代執行完 step 2-6 checkpoint 後，runtime 判斷：

- score ≥ target → 進入 step 7 commit (success path)
- budget 用盡（generation 數或 wall-clock）→ 進入 step 7 commit (evidence_only path)
- control_signal pause → 暫停（task lifecycle_state='paused'，working dir 保留可 resume）
- 其他 → 回 step 2 跑下一代

Outcome：

```
proved_with_construction  — 找到 score ≥ target 的 instance，G 直接 silver verdict
evidence_only             — budget 用盡無合格 instance，留 best-known 在 evidence
unproductive              — agent 寫不出有效 candidate generator / spec 不可機械評估
exhausted                 — type-check / compile retry 用盡
```

Outcome 分類：前兩屬 success class；後兩屬 failure class。

**行為規則**

- **Budget**：atomic 模式預設 100 代（`construction_atomic_budget_generations`）；continuous 模式預設 4 hour wall-clock（`construction_continuous_budget_wall_clock_sec`）。Strategist inject 時可在 decision payload 內覆寫
- **Mutation operators**：框架預先註冊（small_random_change / column_swap / lean_synth），Goal 可在 `question.mutation_operators` 加客製 operator override
- **Trust set**：proved_with_construction 的 Goal `trust_set` 含 `kind=computational` entry，metadata 帶 evaluator_hash + generation + seed（reproducibility 必要）
- **Cancellation**：找到合格 instance 後 cancel G 還在跑的 Builder / Backward / 其他 ConstructionSearch；**spawn 出的輔助 Goal 對應 Builder 不 cancel**（保留升級機會）
- **Best-known promotion**：每 checkpoint 若 best_score 改進就同檔覆寫 Library/Constructions/<G>.json——崩潰最多丟 5 min 內進度
- **Crash recovery**：crash 後 task 從 last checkpoint 接續，不從第 1 代重跑
- **共用 Evolution subsystem**：演化 loop 機制走 v3 §4.3 Evolution subsystem
- **Strategist signals 觸發**：score plateau（連續 ≥ 20 代無改進，`construction_score_plateau_generations`）→ 弱訊號換 mutation operator 或 Shelve；score 達 target × 0.95 → 強訊號加碼 budget 衝最後一哩

---

## 8. Generalizer

讀一個已 proved Goal G，寫候選 generalization G\*——更廣命題使 G 是其特例。G\* 入池走 normal attack（Backward / Builder）；證成功就成 Library 內更廣定理。

**速查**：

| 維度 | 值 |
|---|---|
| 觸發來源 | **Strategist inject only**——架構唯二「無 structural refill 自動派」之一（另一是 Forward）<br>**理由**：對每個 proved Goal 都派 Generalizer 會炸 token；需 LLM 看 inventory 判 Goal 結構是否有 generalize 潛力<br>**Contingency hard rule** 同 Forward：proved root 累計 N 次 / idle T 分鐘無 Generalizer 派出 → reactor 強制 inject（hardcoded、P7 default 不開） |
| Runtime / Pool | atomic / P（atomic pool） |
| 預設 model | 未明定（agent stage 寫 G\* statement）；建議走 sonnet 級 |
| 被 cancel 時機 | 無（Generalizer 跑時不依附特定 Goal terminal verdict） |
| 對外 cancel | 無 |
| `no_novel` outcome | dup → discard、不算失敗、不寫 dead_attempts |
| `unproductive` outcome | **不寫 blocked_pipelines**（跟 Counterexample 不同）：Generalizer 的 unproductive 來自 LLM 主觀判斷「G 不適合 generalize」，不是結構性不可能。保留 Strategist 反覆派彈性（agent 可能後來改變判斷或不同模型有不同看法） |
| 自動 cascade | **無**——G\* proved 後**不**自動把原 G 標 proved（需 Cluster typed relation 機制，留 P8+） |

Stages：

```
1. failure_replay   (pure)   讀 dead_attempts（target_kind=generalizer）
2. agent            (agent)  讀 G 的 statement、寫候選 G* statement
                             early-exit unproductive：agent 判 G 不適合 generalize（已是最廣形式 / 結構不允許 abstract）
3. self_verify      (pure)   驗 G* statement type-checks
                             [fail → retry from step 2]
4. dedupe (any)     (pure)   G* vs Mathlib + Library + goals 全去重
                             dup → discard（不算失敗）
5. commit           (pure)   - novel：INSERT goals (G*, origin='generalizer', kind='theorem',
                                                   depth=0)
                                       + mv staging .lean
                             - dup：no-op
```

Outcome：

```
success         — G* 入池為新樹根
no_novel        — 候選跟既有重複
unproductive    — agent 早退（G 不適合 generalize）
exhausted       — self_verify retry 用盡
```

**行為規則**

- **Strategist signal**（agent prompt 內建）：
  - Library/Theorems/ 內有多個結構相似的 root proved → 強訊號該 inject Generalizer 找統一定理
  - Goal proved 後 Strategist 若判其形式有 generalization 潛力（如數值具體值 4 可能可推 ∀ n ≥ N）→ 弱訊號
- **無自動 cascade**：G\* proved 之後**不**自動把原 G 標 proved——當前架構沒 Cluster typed relation 追蹤 G ↔ G\* 關係。要 auto-cascade 需後續 Pack 引入 Cluster
- **Library promotion**：G\* 進 Library/Theorems/proved.lean 走標準路徑（trust_set 通過 Library.whitelist 即可），跟其他 origin 的 proved 一致
- **跟 Forward 的關係**：Forward 推下游 corollary、Generalizer 推上游抽象——兩 pipeline prompt 設計不同，互不替代
- **unproductive 不寫 blocked_pipelines**（跟 Counterexample 不同）：Generalizer 的 unproductive 來自 LLM 主觀判斷「G 不適合 generalize」，不是結構性不可能。保留 Strategist 反覆派的彈性（agent 可能後來改變判斷或不同模型有不同看法）
