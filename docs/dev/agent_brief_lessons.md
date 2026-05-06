# BRIEF.md + LESSONS.md — context split + agent-curated experience

Status: planned (2026-05-06). 從 Phase 6.5 PN dry-run 觀察到 Context.md 跨
spawn 重複大量 stable 內容、加上「agent 在某個 goal 上學到的東西無法 carry 到
其他 spawn」的機制空缺、整理出兩個檔案的設計。

## 動機

兩個獨立但相關的問題：

1. **Context.md 跨 spawn 冗餘**：每次 dispatch framework 重組 Context.md、把
   Manifest、Sandbox、Library、Mathlib resolved sigs 等 problem-level stable
   內容塞進去。同一份內容跨 spawn 重複、token 浪費（每個 PN spawn 都帶整份
   forbidden_lemmas + Mathlib hints + strategic_notes）。**單純重排 sections
   抗 prompt cache 失敗、無實質幫助**。

2. **Agent 經驗無 carrier**：F22 playbook 在 Phase 3 退役後、agent 在某 goal
   上學到的 cross-spawn 教訓（如 PN 的 `open scoped InnerProductSpace` 漏、
   Mathlib API drift `pow_le_pow_left → pow_le_pow_left₀`）無處沉澱、每個
   新 goal 重撞同一坑。Per-goal annotation（Phase 2）解的是「該 goal 證明過程
   的紀錄」、不是 cross-spawn 經驗。

## 設計總覽

兩個 problem-local 檔，經 Context.md 注入給 agent：

```
Problems/<p>/
├─ Manifest.md           ← 人手 SoT（不變）
├─ BRIEF.md              ← framework auto-render：cross-spawn stable invariants
├─ LESSONS.md            ← agent self-managed：cross-spawn experience
└─ proofs/
```

Agent 仍只讀 Context.md（單檔 read surface），framework `compile_context`
把 BRIEF.md + LESSONS.md 內容 inline 進去。

## 檔案內容劃分

### BRIEF.md（framework-managed）

收當前 Context.md 裡所有 cross-spawn stable 的 sections：

| 內容 | 變動頻率 |
|---|---|
| Sandbox 規則（`_section_sandbox`） | 跨 problem 不變 |
| Manifest forbidden_lemmas | Manifest 改才動 |
| Manifest lemma_hints + resolved Mathlib 簽名 | Manifest 改才動 |
| Strategic notes | Manifest 改才動 |
| Library available（Library/<topic>/ 入口）| Library promote 才動 |

留在 Context.md 的純 goal-specific：goal statement、strategy naming、parent
strategy、prior partial、goal history、proved goals 入口指針（最後一個 半-
stable、暫定留 Context.md、實作時可調）。

**Re-render 觸發**：

- `cli init`（建檔）
- Manifest.md 改動（daemon restart 時 re-render）
- Library promote 完成新項（即時 re-render）

### LESSONS.md（agent-managed）

收 agent 跨 spawn 累積的經驗。內容類型不限「失敗教訓」、也含 success idiom：

| 類型 | 例子 |
|---|---|
| Pitfall | `⟪⟫_ℝ 出現、要 open scoped InnerProductSpace、不然 expected token` |
| Winning idiom | `ZMod bridge 對 wilson 級命題、modular arithmetic 看到先試` |
| Heuristic | `‖a‖ ≤ ‖b‖ 形 goal、優先試 real_inner_le_norm + 除 ‖a‖` |

**格式約束**：

- 單行 ≤ 1 sentence（agent 自律、prompt 引導、framework 不強檢）
- 總筆數 cap N=10
- problem-local（PN 的 lesson 不跨到 cantor、留 cross-problem 給 Library 階段）

## Reflection 觸發機制

### 觸發點：每個 successful pipeline 終端

對應該 kind 的 session terminal（success 清 session_id）：

- Builder Phase 2 lake build pass → reflect
- Builder Phase 1 hint pass → 跳過（無 agent、無 session）
- Backward 策略 commit success（含 Phase 6.5 leaf-bypass）→ reflect
- 失敗 pipeline → 不觸發（agent 沒成功 lesson 可萃）

PN 級題目估算：~30 reflection call（21 goal × ~1.5 successful pipeline）。

### Spawn 機制

framework 在 successful pipeline 結束後、`--resume <session_id>` 同 session
起 brief reflection spawn：

```
prompt 大致：
  你剛 successfully <Builder/Backward><goal>.
  Current LESSONS.md content:
    <inline LESSONS.md>
  Reflect: 這次過程有沒有 cross-spawn 值得保存的經驗？
  - 沒有 → 直接 exit、不動 LESSONS.md
  - 有 + cap 沒滿 → Edit LESSONS.md append 一行
  - 有 + cap 已滿 → 自己判斷新 lesson 是否優於最弱既有；是的話 Edit replace、否則 skip
```

**LLM cost 設計**：1 spawn = reflect + decide-keep-or-evict 一次到位。
舊 playbook 是 extract（無條件）+ curate（必要時）兩 call、新機制壓到 1 call、
且大部分 spawn 結果是 noop（agent 自選不寫）。

### Curate 由 agent 主觀判斷（不 mechanical）

舊 playbook 用 LLM judgment 評優淘汰、Phase 3 砍掉是因為 always-on extract
tax、不是 judgment 本身有問題。新機制保留 LLM judgment（agent 在 reflection
spawn 內一次決定）、但只在 `cap 滿 + agent 有 candidate` 兩條件成立時觸發、
省掉 always-on cost。

## Manifest / BRIEF / LESSONS lifecycle

```
Manifest.md（人手）
   │
   │ cli init / Manifest 改 / Library promote
   ▼
BRIEF.md（framework auto-render）
   │
   │ inline
   ▼
Context.md（per-spawn）─── inline ────── LESSONS.md
   │                                       ▲
   │                                       │
   │ [Read]                                │ [Edit tool, reflection spawn]
   ▼                                       │
agent ─── primary spawn ──── pipeline ─── successful → reflection spawn ──┘
                                              ▲
                                              │ --resume same session
```

| 動作 | 觸發者 | 寫入時機 |
|---|---|---|
| Manifest.md edit | 人手 | 任意 |
| BRIEF.md render | framework | cli init / Manifest change / Library promote |
| LESSONS.md edit | agent (Edit tool) | reflection spawn 內、agent 自選 |
| Context.md compile | framework | 每個 dispatch 開始 |

## 失效防護

- **Lesson 過時 / 寫錯**：下次 reflection spawn agent 看 LESSONS.md 自己判斷
  替換；人手也可手動編輯 LESSONS.md 修正
- **Reflection spawn timeout**：best-effort、framework 不阻擋 pipeline 正常
  cascade、跟現有 F55 postmortem 同樣 swallow exception
- **agent 不寫**：自然降級為原本沒 LESSONS 的狀態、不影響 primary 流程

## 相對於 Phase 3 退役 playbook 的差異

| 維度 | F22 playbook（已退役） | BRIEF + LESSONS（本提議）|
|---|---|---|
| 內容類型 | "winning idiom" 單一 | pitfall + idiom + heuristic 三類 |
| 觸發 | per-Verify-success（無條件 extract）| per-successful-pipeline（agent 自決寫不寫）|
| Extract 方法 | 兩個 LLM call（extract + curate）| 單個 reflection spawn 一次到位 |
| Eviction 方法 | LLM judgment | LLM judgment（保留品質）|
| 寫入位置 | playbook.md（獨立） | LESSONS.md（agent owns） |
| Always-on cost | 高（每次 Verify 必跑）| 低（reflection 大半 noop）|
| 跟 BRIEF.md 關係 | 無 | LESSONS 跟 BRIEF 並列、注入同一 Context |

## 實作階段

| 階段 | 內容 | Commit |
|---|---|---|
| A | 抽 Context.md 的 stable sections 進 `BRIEF.md`、cli init / Manifest 改 / Library promote 觸發 re-render | TBD |
| B | 加 `LESSONS.md` 空檔機制 + Context.md inline 邏輯（agent 看到 BRIEF + LESSONS 內容、單檔 read surface）| TBD |
| C | 加 reflection spawn（success pipeline terminal、`--resume` 同 session、prompt 引導 agent 自管 LESSONS.md）| TBD |

A + B 可一起做（pure 架構調整、無 reflection），C 是新 feature 可獨立驗證。

## 開放決策點（待實作前再敲定）

1. **檔名**：`BRIEF.md` / `STABLE_CONTEXT.md` / `PROBLEM_BRIEF.md` 哪個？
   傾向 `BRIEF.md`（短、per-problem-dir 已有 namespace）。
2. **Proved goals grep entrypoint section 歸屬**：放 BRIEF（半-stable、跟其他
   stable 一起）還是 Context.md（每次 spawn 重算）？傾向 Context.md（count 變
   動頻繁、放 BRIEF 要每個 proved 都 re-render BRIEF、麻煩）。
3. **LESSONS.md cap N**：建議 10、需實證調整。
4. **Reflection prompt 細節**：怎麼引導 agent 判斷「值得寫」vs「skip」、避免
   filler 寫；參考 F55 postmortem prompt 風格。
5. **失敗 pipeline 是否觸發 reflection**：當前設計只在 success 觸發、但
   失敗 pipeline 也可能有 cross-spawn lesson（「這條路試過、別人別走」）。
   傾向先不做、實證 success-only 是否夠覆蓋；不夠再擴。
6. **Cross-problem lesson sharing**：當前 problem-local。長期 Library 階段
   可能要加 cross-problem 同 topic 的 lesson 庫。本階段不做。
7. **BRIEF.md 是否實際存在 disk vs 純內存生成**：disk 多一個檔的 lifecycle
   要管；純內存無 inspectability。傾向 disk（人手可 cat 看 agent 看到啥、
   debugging value）。

## 跨參考

- 退役的 F22 playbook：Phase 3 commit `5be9a33`（`Tooling/playbook.py` 已刪）
- Context.md 當前 sections：`Tooling/context.py:compile_context` + `architecture.md` §12
- F55 postmortem 機制（reflection spawn 範本）：`Tooling/pipeline/__init__.py:_attempt_postmortem`
- Phase 6 single-output 設計（agent-write 機制範本）：`docs/dev/goal_naming_annotation.md`
- Phase 4 grep entrypoint 精神（agent 自食其力）：`Tooling/context.py:_section_proved_goals`
