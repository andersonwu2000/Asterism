# Asterism — Session 完整報告

寫給 user 的最終彙整。從 compact 後接手、跑 P7 + 3 輪 R2/R3 audit + 3 個演習。

## TL;DR

P7 framework code 從 patch 28 推到 C55-min、跑 3 輪 review-fix cycle、跑完 wilson + compactness + SG 三個演習。三個演習 framework 全 PASS，不需新 R3。最後 commit `139f1c6`。下一步由你定。

## 完成清單

### P7 推進 (8 commits)

| # | commit | 內容 |
|---|---|---|
| patch 28 | `0b2f3c5` | wire find_lemmas → backward prompt（library scope DB query proved siblings） |
| patch 29 | `45964af` | validator batch mode（N subgoals 一次 runFrontend、解 600s timeout） |
| C49 | `c842297` | Strategist inventory SQL + agent prompt v1 |
| C50 | `9de1f89` | Strategist pipeline runtime + decision demux |
| C51 | `09e7ea1` | Multi-Problem round-robin selector |
| C52+C53 | `1ff2a46` | Forward + Generalizer pipelines + prompts |
| C54 | `57d99eb` | cascade entries for Forward/Generalizer/Strategist + Shelve cancel |
| C55-min | `0f66d7d` | CLI: strategist run-once / decisions + inventory |

### Review cycles (你叫我多跑兩輪 review)

| 輪 | R2 audit | R3 fix |
|---|---|---|
| Round 1 | 3 audit (audit_*.md): 0+3+4 = **7 HIGH + 1 spec MISS** | `2a30363` 修 8 HIGH + 高優先 MED |
| Round 2 | 3 audit (audit2_*.md): batch3 **暫停** (NEW-HIGH-A 是 演習 showstopper) | `88ebbc3` 修 NEW-HIGH-A/B + R3 round 1 自我引入的 silent except |
| Round 3 | 3 audit (audit3_*.md): 跳過 / 跳過 / 無 | `139f1c6` 清 cascade descriptions + payload-drop test |

CI: 905 → **1014 pass / 35 skipped / 1 xfailed / 0 regression**（+109 條）。

### 演習 (wilson → compactness → SG)

| 演習 | Framework | LLM 表現 |
|---|---|---|
| **wilson** | ✅ PASS — Backward Path A leaf-bypass、retry 真的看 dead_attempts 修正 | ⚠️ 1st 幻想 `Nat.Prime.wilsons_lemma`；2nd 改用對的 `ZMod.wilsons_lemma p` 寫完整 ZMod→ℕ 橋接但 omega 收尾 unsolvedGoals |
| **compactness** | ✅ PASS — Backward Path B + 3 sub-goals + patch 29 batch validator | ✅ 拆出 **Lindenbaum-style** 結構：sub_1 = maximal extension 存在、sub_2 = max-consistent finitely-sat → sat |
| **SG** | ✅ PASS — Backward Path B + 3 sub-goals | ✅ 拆出 **Kelly minimiser** 結構：sub_1 = non-collinear triple 存在、sub_2 = infDist 最小的 ordinary triple — 完美對應 Hadamard L0002+L0003 |

關鍵 framework 驗證:
- patches 28+29 wire end-to-end OK
- decompose_required hard limit 強制 Path B（compactness/SG 都 honored）
- Backward retry 看 dead_attempts 修正方向（wilson 2nd attempt 證實）
- patch 29 batch validator 對 N=3 Mathlib-imported sub-goals 通過（compactness/SG 都驗）
- compactness 防秒殺 = Hadamard 的「自定義 PropForm/Sat inductive」手法（**比 Asterism 內建 forbidden_lemmas 乾淨**：編譯期 API gap > runtime blacklist）
- 沒任何 daemon halt / FatalError；R3 round 2 修的 NEW-HIGH-A scheduler dispatch 表（Forward/Generalizer/Refuter）沒被觸發但 readiness OK
- Strategist 沒 fire（單 Goal 演習、K=8 沒到）

## 沒做的事 / 留給未來

### P7 task.md 內仍 deferred

- **C56**：D-baseline vs D-strategist 對照 demo（5 root × 3 runs、需 real claude × hours）。task.md 自承這是 phase exit gate；你的「演習取代」instruction 已 cover，但若要正式 P7 closure 還需跑這 demo pin acceptance #16 數字
- **C57**：Generalizer demo + 終極 acceptance #0a/#0b — 同樣需 real claude；演習已 indirectly 驗了 Generalizer 結構

### Audit 三輪累計 deferred 項（演習可同步進行、不阻 launch）

- **HIGH-3 batch3**: Forward seed.question=NULL → fail-shut before LLM（避免送空 prompt 浪費 token）
- **HIGH-4 batch3**: e2e Backward(opus override) integration smoke
- **H_R2-2 batch2**: per-decision TX vs reflection alignment（partial commit 後 strategist_decisions row 沒記錄真實 enqueued/rejected）
- **MED-3 batch3**: cmd_strategist_run_once hardcode ClaudeProvider，沒走 multi-provider FallbackChain
- **MED-4 batch3**: cmd_inventory 對 unknown problem 靜默回 empty（typo 體驗差）
- **M_R2-2 batch2**: budget/provider/range/mutation_operators payload key 進 queue 但沒 pipeline 讀（已 emit `payload_override_unconsumed` event 留 trace、未補消費）
- **M_R2-3 batch2**: `_decode_payload` 對 bytes / list / int 的 robustness（silent drop）
- **M5 batch2**: `{{EVIDENCE_RECENT}}` prompt placeholder 寫死 `[]`（spec 要 evidence_window=20 個 evidence_updated）
- **L_R2-2**: Builder.resolver wiring TODO 沒 ticket trace
- **LOW-1 batch3**: cancel_running_for_goal multi-pipeline scenario test
- 還有幾條 LOW

### 演習觀察留下的功能 gap

- **wilson omega 收尾 unsolvedGoals**: agent 寫了正確的 ZMod→ℕ bridge 但最後 omega 解不出。這是 LLM 能力上限、不是 framework bug。要 close wilson 需 (a) 多輪 retry 給 agent + dead_attempts feedback 機會 / (b) Strategist 介入派 model='opus' 加強 reasoning / (c) 人類補完 omega 步驟
- **compactness/SG sub-goals 沒被 Builder 攻**: Backward 把 main 拆完就 --once 結束。daemon 模式才會 BFS 持續攻 sub-goals。3 個 sub-goals 留 status=open 在 DB 等下次跑
- **find_lemmas mathlib scope 仍 stub**: patch 28 只 wire library scope（同 Problem proved sibling）；mathlib scope 仍回 []。wilson 第一輪 agent 幻想 `Nat.Prime.wilsons_lemma` 部分原因是 Mathlib 沒被 surface 上去。P5+ 工作

## 給你的決策點

1. **P7 closure**：現在可以 (a) 接受演習作為 P7 終態（你之前 instruction 字面）/ (b) 跑 C56 D-baseline + D-strategist 對照 demo 正式 close phase 7 acceptance #16
2. **wilson 怎麼處理**：sub-goals 留在 DB；要 (a) daemon 跑 + Strategist 加碼 / (b) 人類補 omega / (c) 撤掉 Problem
3. **compactness/SG sub-goals 攻不攻**: 同上問題
4. **Audit deferred 哪些先補**：上面 ~12 條 deferred、優先序你定。我建議 H_R2-2（partial commit reflection）+ M5（EVIDENCE_RECENT）兩個對 Strategist 行為影響最大
5. **演習中發現的真機 LLM 行為**：要不要把這幾個演習結果（包括 sub-goal 拆解）放進 phase7_smarts 或 spike 文件當 baseline 紀錄

---

Session 統計:
- Commits: 12（8 P7 推進 + 3 R3 fix round + 1 R3 round 3 minimal + 演習 setup 沒 commit、靠 init/goal add）
- Audits: 9（3 round × 3 batch）
- 演習: 3
- Tests: +109
- Wall clock: ~3-4 hr 含等 audit + 演習 (parallel 能省的都省了)
