# Asterism 研發日誌

從 zero 開始的逐日紀錄。涵蓋 Hadamard 原型期 + Asterism v2 重構期。

## 第一階段：Hadamard 原型

**2026-04-24（36 commits）**

- 從零打造一套讓 AI 寫 Lean 證明的系統：多 AI 角色分工（提策略、寫
  證明、查文獻），輸出餵給 Lean 編譯器驗證。
- 並行發送機制成形（同題目多條子目標同時跑）+ 多層協調（避免
  agent 互相破壞、自動偵測重複工作）。
- 自動證掉 5 個經典定理：Cantor 對角線、Euclid 質數無限、AM-GM、
  Wilson、命題緊緻性。
- 額外證掉 Hardy 的「無理數的無理數次方有理」+ Mathlib 100 大
  定理裡的 √2 無理跟二項式定理。

**2026-04-25（6 commits）**

- 框架硬化：lockfile + 守護 watchdog + dedup 防呆 + event sourcing。
- agent 自驗機制（寫完 tactic 自己過 Lean 一遍再交）。
- **首次自動證掉 Sylvester-Gallai**（非平凡的組合幾何定理、4 層
  decomposition、16 個子目標）。

## 第二階段：Asterism v2 重構

**2026-04-28（無 commit、不算入逐日紀錄）**

- Asterism v1 寫了一天、發現架構不行、整個打掉。

**2026-04-29（5 commits）**

- 從零起 Asterism v2：把「分解目標」跟「填證明細節」明確拆成兩個
  角色（Backward / Builder）。
- 防呆：sorry-stub guard、WAL 寫入、崩潰恢復。
- 起手 pytest coverage 給純函數。

**2026-04-30（30 commits）**

- 並行架構主體：能同時嘗試多條分解路線（誰先成功誰贏）。
- Deduper v1→v3：靠 Lean 內核的「定義相等」自動辨識重複子目標、
  跨 strategy 共享。
- 框架自我整理：偵測孤兒 attempts dir、清遺留 backup 檔。
- e2e 證掉 3 題：compactness（~60 min、12 並行）、Wilson、
  Cantor。

**2026-05-01（29 commits）**

- 給 AI 接上 Mathlib 知識庫：寫前先查名字、簽名、相鄰引理。
- Context 文件 lazy-load + 大批 prompt 精簡（節省 cache budget）。
- 重試延續：同一個 AI 對話跨多次嘗試保留上下文。
- 接入 Gemini 當第二後端、可逐 pipeline 選不同模型。
- Haiku 模型首次自動證掉 Wilson（弱模型 e2e 里程碑）。

**2026-05-02（27 commits）**

- 操作介面成形：命令列工具（reset / status / doctor）+ 集中式
  config（Asterism.yaml）+ 操作員 vs agent 文件分流。
- agent 沙箱強化：限制 cwd 在單題目錄、不亂讀別處。
- API 配額用盡的應變：偵測到 quota exhausted 不重試浪費、自動降級。
- 模型試驗：用 Opus 證掉 compactness。
- two-phase delivery 實驗（agent 先交骨架、再填細節）── 試了
  revert，效果沒預期好。

**2026-05-03（18 commits）**

- 明確的「不可證」訊號：agent 可以主動宣告子目標 infeasible 並附
  反例、框架直接 shelve、不再反覆失敗。
- Library promotion：證完一題後結果自動進共享 library、給未來
  題目當引理。
- 給 agent 兩個搜尋工具：Grep（mathlib 名稱搜）+ Loogle（按
  type pattern 搜）。
- 「骨架→填洞」decomposition 機制：Backward 寫好骨架 + sorry stub、
  Builder 各自填。
- 加 5 個新測試題：proj_nonexpansive、inner_zero_iff_smul、
  cantor_xi_measure、localization_euclidean、SG。

**2026-05-04（26 commits）**

- 失敗處理大改：spawn 超時被殺後、自動再起一個 agent 寫「進度
  報告」、partial work 不丟。
- 砍掉獨立的 Verify pipeline、改成框架內建步驟（不佔 worker 槽）。
- mathlib 讀取權限：把 `--add-dir` 加到 mathlib packages、agent
  能 grep mathlib 原始碼。
- 第一輪 dispatcher 整合測試 + 一輪 review 修補（P0/P1/P2 batches）。

**2026-05-05（16 commits）**

- **Asterism 首次自動證掉 Sylvester-Gallai**（4h 16min、用 Lean
  預設 3 條公理）。
- 思考時長上限：給 agent 設 1K tokens/min 的 thinking budget、
  防止陷入無止境推理。
- entry_kind 直接化：把「子目標難度 1-5 數字」改成「直接標
  Builder/Backward」、agent 預判更準。
- Infeasibility escape：agent 識別到原命題不成立時、能在當下 spawn
  內構造反例 + 跳出。

**2026-05-06（41 commits、最忙一天）**

- Phase 7 重試大改：同一 AI 對話跨多次嘗試延續上下文（不是每次
  從零讀 Context、節省 prompt cache）。
- goal_naming：子目標名字從 `s001` 改成人類可讀的（例
  `kelly_minimizer_is_ordinary`）、forensic 跟 prompt 都更乾淨。
- 葉子直接交付：允許 agent 在能直接寫完整 proof 時交「無 sub-goal
  的 strategy」、不強制拆解。
- 大幅文件重構：架構文件從 implementation-first 改成 concept-first。
- **Opus 模型重證 SG**（2h 48min、比 Sonnet 快 1.52×）+ PN
  e2e 驗 Phase 1-4 整合。

**2026-05-07（18 commits、跨日完成）**

- BRIEF + LESSONS 雙文件：每題穩定背景文 + agent 自累積經驗文、
  跨 spawn 共享。
- Reflection 機制：成功 spawn 結束時自動 reflection 寫入 LESSONS。
- **LSP swap**：agent 寫證明時跟在背景常駐的 Lean server 即時
  對話、改一行就立刻知道對不對（之前是寫完整檔 → compile →
  讀錯誤 → 改、循環慢）。Builder + Backward 都接、外加
  validate_file 工具讓 agent 驗 sub-goal stub。
- Axiom 檢查單一閘門：每個被標 proved 的子目標都過 axiom probe、
  確保不依賴 sorry。修補了 leaf-bypass 路徑的漏洞。
- 看守機制：把「思考字數上限」換成「無動作偵測」── 12 min 內沒
  呼叫工具就殺、最後 3 min 讓另一個 agent 接手強制交付。

**2026-05-08（spike 階段、進行中）**

- **今日主攻：Lean server 共用**。現況每個 agent 各起一個 Lean
  server、Mathlib 在每個 process 裡都有一份 elaborated 結構、
  4 並行就吃 12-20 GB RAM、想拉到 8+ 並行直接撞 RAM 牆。
- 架構決定：daemon 啟動時起 1-2 個常駐 Lean server、所有 agent
  排隊用同一個、並行度跟 RAM 預算解耦。
- Spike 驗了關鍵風險：claude 的工具協議（MCP）支援 HTTP 模式、
  單一 server process 能同時處理 3 個並發 agent 的 tool call、
  call counter 累加正確、無 race。
- Gateway 架構不再有技術 unknown、剩 2-3 天工程實作。

---

11 天 zero → 自動證掉 Sylvester-Gallai、現在在拆掉並行度的 RAM
上限。
