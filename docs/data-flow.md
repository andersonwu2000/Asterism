# Asterism — 資料流向

寫於 2026-05-04，反映 F55 + F56 後的形狀。

## 為什麼需要這份文件

Asterism 的 agent 是**外部 process**（claude / gemini CLI），框架透過寫檔給它讀、它寫檔回來框架收的方式溝通。資料在 DB、磁碟暫存區、永久檔案間來回，三個介面要對得上才不會看不到彼此。這份文件用流程角度說明每塊資料**誰寫、誰讀、為什麼放在那裡**。

讀完這份能回答：
- 一次 agent 失敗後，下一次它怎麼知道上次發生了什麼？
- timeout 把 process 殺掉之後，agent 思考到一半的內容怎麼救？
- 一個 strategy 的 sub-goal 全部證完後，誰負責把它組裝成 parent goal 的證明？

---

## 三層儲存

| 層 | 位置 | 壽命 | 用途 |
|---|---|---|---|
| **暫存** | `.attempts/<pipeline_id>/` | 一次 spawn | agent 當下讀寫的工作目錄；spawn 結束就刪 |
| **跨 spawn 持續** | `Problems/<p>/.drafts/<kind>_g<gid>.md` | 該 goal 證完前 | 上次 timeout 後 agent 留下的進度筆記 |
| **永久** | DB + `Problems/<p>/proofs/L_*.lean` | 與 problem 同壽 | 已證的 sub-goal、strategy patch、所有歷史紀錄 |

設計理由：暫存區隨 spawn 拋掉、保證每次乾淨起手；跨 spawn 層只放「需要傳給下次的 agent」的東西；永久層是真實狀態的單一來源。

---

## 一輪 spawn 的成功路徑

以 Backward worker 為例。Builder 結構幾乎一樣（差別在沒有 sub-goal、只有一個 patch 檔）。

```
框架側準備：
  1. 從 DB 編 Context.md（goal 敘述、命名規則、過去失敗摘要、Mathlib 提示...）
  2. 預寫 patch.lean 框架（鎖死 theorem signature、body 留 sorry）
  3. 從 .drafts/ 讀上次 timeout 留的進度筆記（如有），併入 Context.md
  4. 把 Context.md + patch.lean 放進 .attempts/<pid>/
  ↓
Spawn agent (claude --session-id <uuid>)：
  5. agent 讀 Context.md
  6. agent 視情況讀 PAST_ATTEMPTS.md / PAST_BACKWARD.md（深入查證需要）
  7. agent 用 Grep / Loogle 查 Mathlib
  8. agent 改 patch.lean 的 body、寫 PROPOSAL.md、寫 N 個 new_*.lean（sub-goal 骨架）
  ↓
框架側收尾：
  9. 驗 patch.lean 簽名沒被改、檔名規範符合
  10. 把檔案搬到永久位置 Problems/<p>/proofs/
  11. lake build 一次（含 sub-goals 的 sorry stub），確認組裝合法
  12. INSERT goals/strategies/strategy_subgoals 進 DB
  13. 刪 .attempts/<pid>/、清掉 .drafts/（這次成功了，沒理由留）
```

關鍵：**agent 看到的東西全部由框架預編進 Context.md**（F43）。companion file（PAST_ATTEMPTS / PAST_BACKWARD）只是備援的「翻閱用」深查資料，agent 經常不會主動讀，所以**重要的訊息一定要 inline 在 Context.md**。

---

## 失敗路徑

### 普通失敗（rc≠0、非 timeout）

例如 lake build 沒過、agent 寫的 patch 引用不存在的 lemma：

```
spawn 結束、agent 退出 rc=1
  ↓
框架記下：
  - 把 attempts dir 裡的檔案打包進 dead_attempts.artifacts (DB)
  - 抽 lake stderr 進 dead_attempts.failure_detail
  - **保留 session_id**（claude session 還活著）
  ↓
下次 dispatch（warm retry）：
  - claude --resume <同個 session_id>
  - 給 agent 一段短 prompt：「上次的 lake error 是 X，重寫 patch」
  - agent 的 session 記憶還在，從上次思考接著做
```

這是 F33（Builder）/ F53（Backward）的 warm-resume 機制。普通失敗不需要持久化任何 partial 內容，因為 session 記憶接得上。

### Timeout（rc=124，process 被 SIGKILL）

session memory 還在（pinned 在 disk），但 process 已死，沒機會把當下思考寫進任何檔。F55 的處理：

```
主 spawn timeout、SIGKILL
  ↓
框架做一次「postmortem spawn」：
  - claude --resume <session_id>
  - 短 prompt（Tooling/prompts/<kind>_postmortem.md）：「你被中斷了，
    用 150 字寫下你考慮的方向、卡在哪裡，存成 _progress.md」
  - 限時 120 秒（避免 postmortem 自己也卡很久）
  ↓
agent 用 session 記憶寫 _progress.md
  ↓
框架把 _progress.md 從 attempts dir 複製到 .drafts/<kind>_g<gid>.md
（attempts dir 接著被刪、.drafts 持久存著）
  ↓
下次 dispatch（cold start，session_id 已清）：
  - 編 Context.md 時讀 .drafts/<kind>_g<gid>.md
  - inline 成「## Your previous progress note」段
  - agent 讀 Context.md 看到自己的回顧筆記、繼續做
```

為什麼不直接讓 agent **邊想邊存** PROPOSAL.md（一開始的 F55 設計）？因為那會讓 agent 同時思考又要維護 deliverable，注意力分裂、容易過早承諾某個分解方向。改成**事後** postmortem 把 deliverable 跟思考紀錄解耦。

為什麼 postmortem 不會也死？兩個保護：120 秒 cap + 任何 rc≠0 都當 best-effort 失敗（next spawn 就 cold start，不比沒 F55 差）。

---

## Verify 收尾（F56）

當一個 strategy 的所有 sub-goal 都證完，需要：
1. 確認組裝起來能編譯
2. 把 parent goal 的 sorry stub 改寫成「我用這條 strategy 證的」

這件事**沒有 LLM 介入**，全是檔案操作 + lake build。所以它不是一個 worker_kind，是 dispatcher 主迴圈的一個收尾步驟。

```
每一輪 dispatcher tick 結束時呼叫 verify_housekeeping：
  loop（最多 8 圈）:
    查 DB：哪些 strategy 的所有 sub-goal 都已 proved？
    若無 → 跳出
    對每條 ready 的 strategy:
      Step 1: lake build _strategy_s<id>.lean
              （strategy 的組裝 patch，import 各 sub-goal proofs）
      Step 2: 把 parent goal 的 lean 檔改寫成 alias
              `def L_main := @Problems.<p>.s<id>`
      Step 3: lake build alias-form parent
      
      三步都過 → strategy='succeeded'、parent goal='proved'
                 觸發鏈式：parent goal 可能又是別的 strategy 的 sub-goal
                 下一圈會撈到那條
      任何一步壞 → strategy='dead'、parent goal attempts++、走 cascade
```

**為什麼遞迴？** 深度 4 的題目可能連帶 4 層 strategy 同一輪 sweep 全部完成。`max_iters=8` 是上限，避免病態情況卡住整個 tick。

**為什麼沒有 F41 LLM 修復？** 之前設計過：Step 1 build 失敗時叫 LLM 修一次 patch。實證 26 次 verify（cantor + proj_nonexpansive）0 觸發 — F52（鎖死 strategy 簽名）+ Backward commit 前先 build 過 sorry-stub，已經過濾掉絕大部分組裝錯誤。再加 LLM 修復是為極罕見事件付架構複雜度的代價，不划算。如果未來實證上 Step 1 開始失敗，再加回來。

---

## 設計取捨速查

| 決策 | 為什麼 |
|---|---|
| Context.md 內聯重要訊息、companion file 只當備援 | F43 教訓：agent 不會主動讀 companion |
| Timeout 走 postmortem 而非邊寫邊存 | 主任務不被 deliverable 維護分心 |
| 進度筆記只保留最近一次（overwrite） | F33/F53 的 session 記憶通常會 incorporate 上次內容；保留多版本目前看資料無必要 |
| Verify 內聯 dispatcher 不佔 worker slot | 純框架操作沒理由佔 LLM pool 的格子 |
| F41 LLM 修復取消 | 實證 0 觸發、不為罕見事件付架構成本 |

---

## 跨參考

- 完整 worker / pipeline / DB schema：`docs/architecture.md`
- 操作員 CLI / 環境變數：`docs/OPERATOR.md`
- 當前狀態 / 最近改動：`docs/STATUS.md`
