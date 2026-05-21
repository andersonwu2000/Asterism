# Decline directives 統合系統

Status: planned (2026-05-10)。取代當前散在 Builder / Backward 各自發明的 ad-hoc
decline directive 詞彙、統一成一層、跨 pipeline 共用。

## 動機

當前各 pipeline 的「agent 主動跳出」指令是各自獨立發明的：

| pipeline | 已有 directive | 限制 |
|---|---|---|
| Builder | `decline: too_hard` / `decline: parent_type_infeasible` | 沒「有錯但可修」這條 |
| Backward | `decline: parent_type_infeasible` | 缺「需 Forward 介入」、「父策略小錯」這類 |
| 未來 Forward / Generalizer | 還沒寫 | 全套要重新發明 |

問題：
- 用詞、語意、解析路徑分散、增刪 directive 要動好幾處
- cascade 端對應 routing 邏輯也散在 `cascade_one` 各 if branch
- 沒共用詞彙、未來新 pipeline 各自重發明、複雜度線性增長
- agent 端面對不同 pipeline 要記不同字面、跨 pipeline 經驗無法遷移

統合的目標：
- 單一 directive 詞彙、所有 pipeline 共用
- agent 端只記 4 個指令 + 自由文字說明、不用記每個指令配什麼欄位
- framework 端集中 parse + route
- 訊息傳遞（descriptions 注入下游 prompt）跟 directive routing 自然耦合、同層管

## 詞彙

### 結構

每個 directive 是一個 token + 一個自由文字 description block。寫在 patch.lean
的 leading comment（同現有 `decline:` 約定的位置）：

```lean
namespace Problems.<problem>

-- decline: <directive>
-- ## ...自由文字說明、由下游 pipeline 解讀...
-- ...可以多行、可以含具體值 / hypothesis 名稱 / 計算 / 反例...
theorem s<id> ... := by sorry

end Problems.<problem>
```

`description` 不強制欄位結構 — 下游 pipeline 帶模型智能、能讀懂自由文字。
parser 只抓 `directive` enum + `description` 整段 markdown text、不做 schema 驗證。

### 4 個 directive

| directive | 可觸發 | 路由 | description 建議內容 |
|---|---|---|---|
| `不可證` (unprovable) | Builder, Backward | shelve + cascade 上傳；未來可分流到 Strategist 覆核或證偽 pipeline | 反例（具體值 + 算式驗證所有 hypothesis 成立但結論不成立） |
| `返回父` (return-to-parent) | Builder, Backward | 父 strategy 標 dead → 父 goal 重派 Backward；description 注入父下次 context | 修法提示（缺哪個 hypothesis / 換哪個結構 / 應該怎麼補） |
| `擱置` (shelve) | Builder, Backward | shelve + cascade 上傳；未來 Strategist 可覆核並決定復活 | 為何放棄、之後可能怎麼回頭看 |
| `需拆解` (needs-decomposition) | Builder（Backward 不能） | `entry_kind=Backward` + attempts++、下次派工路由到 Backward | 為何 Builder 做不到、若可給拆解方向提示 |

Backward 直接證（leaf-bypass）**不**升級成顯式 directive、繼續由框架 leaf-bypass
路徑承接 — 那是「越權成功」、不需要 agent 主動表態。

## 路由詳解

### 不可證 / 擱置

行為相同（目前）：
- `goal.status = 'shelved'`
- `goal.attempts++`
- `_propagate_shelve(goal_id)` cascade 到父 strategy → 父 goal 重新可派
- 父下次派工的 context 含 `infeasible_subs` 投影出該子的 description

差別只在語意分類、留給未來 Strategist 區分覆核策略。

### 返回父

- 該 sub-goal 的 strategy 被 `dead` 標記（同 cascade infeasible 路徑）
- 該 sub-goal `goal.attempts++` 但 status 維持 `'attempting'` 或反開 `'open'`
  讓父收到信號（細節見「Cascade 互動」章節）
- 父 strategy 標 `dead`、父 goal `status='open'`、attempts++（保留現有 1:1
  attempts ↔ dead_attempts invariant）
- 父下次派工 context.md 含特殊 section `## Fix hint from prior shelved sub-goal`：
  - 列出 sub-goal slug + 它的 directive + description 全文
  - Backward prompt 加新規則：「若 context 含此 section、優先嘗試保留前次 strategy
    shape 並按 hint 修正、僅在 hint 明示需要結構性換 shape 時才換」

如果父也搞不出來、父最終會 attempts 撞 `SHELVE_THRESHOLD` 自然 shelve、cascade
繼續上傳到祖父。

### 需拆解

- `goal.entry_kind = 'Backward'`
- `goal.attempts++`、status 維持 `'open'` 或反開
- 下次 `next_worker_kind(goal)` 看 entry_kind 派 Backward
- description 注入下次 Backward spawn 的 context（替代現有 `agent_declined`
  在 `direct_attempts` projection 中的呈現）

對應現有 `decline: too_hard` + `cascade_one` 的 `agent_declined` branch。改名
+ 統合 description 處理機制、不是新發明。

## Cascade 互動

### 子寫返回父時、父 strategy 該死嗎

**目前定案：父 strategy 標 dead**。

理由：父策略既然產出有問題的 sub-goal（即便只是漏 hypothesis 這種小錯）、
它在 DB 表上被視為「曾活過、未來可能可救」會讓 strategy 表 dirty、
`strategies_ready_for_verify` / dedup 等查詢要多濾條件。死掉乾淨。

父重派時看到 dead 的舊 strategy（在 `direct_attempts` / `dead_strategies`
projection 中）+ 新 hint section、自己決定走「保留 shape 補 hypothesis」還是
「換 shape」。description 帶的 fix 提示足以引導、不需保留 dead strategy
就能做 incremental fix。

### 開放議題：Backward 編輯舊 strategy .lean

替代設計：父 strategy 不死、Backward 重派時帶「fix 模式」、agent 直接編輯
`_strategy_s<id>.lean` 的 patch 部分（增加 hypothesis extraction、改 combinator 應用）、
而非寫一份新 strategy。

優點：
- 比寫整份新 strategy 改動量小、agent 容易做對
- 顯式表達「這次只是補洞、不是換思路」、避免 agent 不必要的 shape 漂移

缺點：
- 改動既有 DB strategy row 的 lean_path 內容、需要 schema 思考（versioning？）
- 若編輯失敗該怎麼回退、語意比「strategy dead → 寫新的」複雜
- 跟 dedup / library promote 的互動要重想

**目前不做**、留作 v2 議題。等 v1（strategy 死 + hint 提示）跑一輪看 agent
實際行為再決定。

### Cascade 順序保留

新 directive 系統的 cascade 邏輯仍走現有 `cascade_one` + `verify_housekeeping`
路徑、只是 `failure_reason` 細分到 directive level、routing switch 多幾條 case。
跟 `5bded83` 的 cascade-vs-verify race fix 相容（has_live guard 不依賴 directive
分類、純看活策略狀態）。

## 邊界問題的處理立場

### 不可證 vs 擱置

兩者目前路由相同（shelve + cascade）、語意差別：

- **不可證**：agent 找到反例、附證據
- **擱置**：agent 沒找到反例、純粹當前資源不夠

實務上 agent 可能誤分類、邊界模糊。**目前不強制驗證一致性**：
- 寫不可證但無反例 → parser 接受、僅在 description 缺反例時記一個 warning 標記
- 寫擱置但有反例 → parser 接受、不強制重寫

理由：硬性規範會讓 agent 為了塞模板而犧牲訊息品質。soft 設計留給未來
Strategist 做覆核 — 它讀 description 內容自己判斷是不是該升級為不可證。

### 返回父 vs 不可證

返回父 = 「修父就能證」、不可證 = 「父對不對都救不了」。

agent 可能誤分類（過度樂觀以為修父就能救、實際上不可證）。**不嚴查**：
- 返回父後父重派 Backward、新 attempt 若仍失敗（包含再寫不可證 directive）、
  attempts 累積撞 SHELVE_THRESHOLD 自然 cascade up
- 整條鏈最終由 attempts 上限 + cascade 機制收斂、即使 directive 誤用也不會無限循環

### 需拆解 vs 返回父（Builder 視角）

需拆解 = 「我（Builder）能力不足、換 Backward 拆」 — fix 在這條 line（換 worker kind）
返回父 = 「Builder 看出這條 line 上面有錯、要改父」 — fix 在上一層

清楚、不太會混淆。需拆解的 description 可以提示拆解方向（例如「應該按 case
分支、不是 induction」）、Backward 派工時讀。

## 跟現有 failure_reason / DB schema 的對應

DB schema 不變（避免 migration）：

| 新 directive | 持久化 failure_reason |
|---|---|
| 不可證 | `agent_infeasible`（舊名沿用、parser 維持 alias）|
| 返回父 | `parent_needs_fix`（新值、加進 `failure_modes.md` §2 enum） |
| 擱置 | `agent_shelved`（新值；舊 `agent_infeasible` 不附反例的退化路徑改投 here）|
| 需拆解 | `agent_declined`（舊名沿用）|

`_extract_decline_reason` 改寫成新 parser、回傳 `(directive, description)`、
其他模組看 directive 路由、看 description 注入。

## 實作步驟

1. **設計 doc 定稿**（本檔）
2. **寫範例 prompt 字句**（草稿、放在本檔附錄、不動 prompts/*.md）
3. **跟使用者對齊 prompt 措辭**（依規則：prompts/ 動工前必先討論）
4. **新 parser** `Tooling/pipeline/_decline.py` 或擴充 `_extract_decline_reason`、
   回傳 `(directive, description)`
5. **舊 enum 對應 mapping**：`failure_reason='agent_infeasible'` 等保留、parser
   能 round-trip
6. **`cascade_one` 改 directive switch**、各 directive 路由邏輯
7. **`context.py` 的 `infeasible_subs` projection 改名 + 增 directive 分類**、
   渲染 `## Fix hint from prior shelved sub-goal` section
8. **prompts/builder.md + backward.md `## Decline` 區重寫**（依步驟 3 的對齊內容）
9. **regression test**：
   - 每個 directive × 路由完整 e2e test
   - cascade 互動測試（子返回父 → 父收到 hint → 父正確路由）
   - directive 誤用 / 邊界 case（不可證無反例、返回父實際不可證等）
10. **跑一次 SG / cantor**、看 agent 自然使用情況、迭代 prompt 措辭

第 3、8 步是 prompt 級改動、屬「先討論再動」範圍。其他可直接動。

## 後續路線（v2+）

### Strategist 介入

當前設計把 directive 留給 agent 自己診斷。Strategist 想做「跨 sibling 整合」、
「shelved 復活」、「呼叫 Forward / Generalizer」這類 agent 看不到的決策時、
基於 directive 系統的紀錄做：
- 讀整顆 cascade 樹的 `dead_attempts.proposal_md`（含每個 directive 的 description）
- 寫 hint 進某 goal 的 context.md（不直接改 DB 狀態）
- 決定何時 spawn Forward / Generalizer

跟本系統不衝突、是「上層覆核」、不取代 agent 自己用 directive。

### Forward / Generalizer 觸發

新 pipeline 加入時、它們也用同套 directive 詞彙：
- Forward 可發 `不可證` / `返回父`（同 Builder/Backward）
- Generalizer 可發 `擱置`（「這個 generalize 不值得做」）
- 哪個 pipeline 能發哪些 directive、在 prompt 端規範、parser 端驗證

### Backward 編輯舊 strategy（前述開放議題）

v1 跑一輪後若觀察到「父重派時還是換 shape 不補洞」就考慮加。

## 不要做

- **多層分類**（intent + subcategory）：當前單層 + 自由文字描述夠用、過度結構化
  反而誘導 agent paralysis
- **強制 description 欄位**：硬性 schema 會讓 agent 為塞模板犧牲訊息品質
- **directive 自動跨多階層傳遞**：一個 directive 只影響直接父；要影響祖父請
  cascade 自然觸發、不要設計直達跳級
- **directive 之間的「升級」自動轉換**：不要在 framework 端把擱置自動升不可證；
  該由 Strategist 上層判斷或 agent 重新發

## 跨參考

- 現有 decline parser：`Tooling/pipeline/__init__.py:_extract_decline_reason`
- 現有 cascade_one：`Tooling/dispatcher.py:cascade_one`
- 現有 infeasible_subs projection：`Tooling/pipeline/events.py:infeasible_subs`
- 現有 too_hard escalation：`Tooling/dispatcher.py:cascade_one` Builder branch
  agent_declined → entry_kind switch
- failure_reason enum：`docs/failure_modes.md` §2
- 跟 `968e4e7`（leaf-bypass acceptance axiom probe）共軌：兩者都減少 agent
  shipping 不該 ship 的東西、本系統補完「ship 但要主動分類」這條
- bridge_lemma_layer.md：v1 directive 的 fix hint 機制能緩解 agent
  「漏 hypothesis 然後換 shape 不補」、跟 bridge lemma 是不同層次補強
