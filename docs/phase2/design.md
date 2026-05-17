# Phase 2 設計 — 總覽

範圍：Asterism 從「攻單一指定 theorem」進化為「自主推進 target、必要時擴 Library」。落兩條新 pipeline、設定 residue theorem 為驗證 target。

不在 Phase 2 範圍：conjecture-kind Goal / cluster relation / verification_level 譜系 / Library typed archive / continuous_task runtime。

本檔放概念與動機、pipeline 細部 spec 在 `pipelines.md`。

---

## 0. 為什麼是 Phase 2

當前 (Phase 1) Asterism：用戶給定 root theorem、framework 用 Backward / Builder 由上而下分解、攻。

Phase 1 的盲點：
- 攻 hard target 時缺中間 lemma 沒人主動補（Mathlib gap 情境）
- Pipeline 派發只有 BFS structural refill、沒有 meta-level 規劃
- 多 problem 並行時資源無人協調

Phase 2 補：
- **Strategist**（首席研究員）：看全圖決定研究方向、調度其他 pipeline
- **Forward**（gap-bridger）：目標導向、補出 target 所需的中間 lemma

---

## 1. Pipeline 整合列表

從 v3 doc 的 13 種收束到 8 種：

| Tier | Pipeline | 角色 | 狀態 |
|---|---|---|---|
| 核心 | **Backward** | top-down decomposer | Phase 1 已有 |
| 核心 | **Builder** | leaf prover | Phase 1 已有 |
| 核心 | **Strategist** | 首席研究員、meta coordinator | Phase 2 |
| 核心 | **Forward** | 目標導向 gap-bridging | Phase 2 |
| Tier 1 | **Refuter** | conjecture 反方攻（含 counterexample mode） | 後續 |
| Tier 1 | **Curator** | Library promote + reorganize | 後續 |
| Tier 2 | **Distiller** | 從 proved 抽 pattern / abstraction | 後續 |
| Tier 3 | **ConstructionSearch** | construction-kind 專用 | research-mode |

合併原則：
- 反方攻擊（Refuter + Counterexample）合一條、兩 mode
- Library 維護（PromotionJudge + LibraryCurator）合一條
- 抽資訊（PatternMiner + Abstractor）合一條、兩 output mode
- ConjectureProposer 與 ConsistencyChecker 下沉到 research-mode、Phase 2 不刻

---

## 2. Strategist 的位置

**定位**：首席研究員。不微管理每條 dispatch、不取代既有 BFS structural refill；只在 BFS 處理不了的 meta 層面介入。

擅長處理的事：
- 派發觸發時機微妙的 pipeline（Forward 等）
- Goal 被 agent 主動 shelve 時、review 是真 dead end 還是可以換方向再試
- 第一條 pipeline 啟動 + 必要時初寫 Defs.lean
- 透過 problem-level directive（單句、覆蓋寫）向其他 pipeline 傳達

不做的事：
- 決定下一條 Backward 派哪個 Goal（BFS 處理）
- 調 queue 優先序（既有 priority 機制夠用）
- 主動 health check / framework alert（未來再加）
- Phase 2 開場「擱置 root」（先 Forward 鋪墊再攻 root）：不開、root 一律先試 Backward、卡住才走 routine 介入

**觸發機制**：
- T0：每 problem 首次（`problems.bootstrap_done=false`）
- T1：wall-clock routine（預設 60 min / 次）
- T2：goal_pending_review event（cascade 偵測 agent_shelved 後改 pending 狀態）

簡化選擇：T1 走 wall-clock 而非 event-counter、因為事件權重不一致時 counter 容易誤觸發 / 漏觸發；wall-clock 預期穩定、`Noop` 決定也廉價。

**人類介入最小化**：Phase 2 只有 `RequestUserAmend(file)` 一個 human-input 入口（user-owned 檔修改提案、`file` ∈ Defs.lean / Manifest.md）；其他狀況 Strategist 自決。Manifest 也涵蓋是因經驗上 Manifest 的 hints / Entry kind 等指示也會錯導向。

---

## 3. Forward 的位置

**定位**：前沿研究 / 主動推進。看當前手上有什麼（Library / Mathlib / 已 proved Goals）、判斷該往哪擴展、產一條對未來通用的新 lemma。Strategist 在 brief 內描述需求方向、Forward 自行判斷該產什麼。

可能輸出：補既有 target 卡點的中間 lemma、抽象工具、mathlib 沒有的特殊 case、generalize 已 proved 結果。

跟 Backward 的本質差異：

| | Backward | Forward |
|---|---|---|
| 方向 | top-down（拆解既有 Goal） | bottom-up（看現狀提新工具） |
| 觸發 | 自動 BFS | Strategist 指定 |
| 輸出 | 直接攻擊用 sub-goal、tie 父 Goal | 通用 lemma、不 tie 任何 Goal、未來多用 |

---

## 4. Strategist × Forward × 既有 pipeline cycle

對 residue theorem 的概念流程：

```
1. cli init residue_thm   → problems.bootstrap_done=false
2. T0 觸發：Strategist 啟動、看 Manifest / Defs / Root、
   commit: InitializeDefs（若 Defs 不存在）+ Noop（或 EmitDirective）
   設 bootstrap_done=true
3. BFS 自動 enqueue Backward(root)、跑、可能失敗（缺中間 lemma）
4. 60 分鐘後 T1 觸發：Strategist 看 inventory、
   commit: Inject(pipeline=Forward, brief="need contour deformation lemmas")
5. Forward 自行判斷產出 1 條通用 lemma 進池（origin=forward、不掛 target）
6. BFS structural refill 派 Backward 攻該 lemma
7. 下次 T1 觸發、Strategist 視情況再 InjectForward、或 Noop 等 Backward 進度
8. 反覆迭代直到 main proved
```

關鍵：
- Strategist 配發 **研究方向**、不直接派 Backward。Backward 全靠 BFS structural refill 派
- Phase 2 內 Inject 只用於 Forward；未來 Tier 1+ 才加 Refuter / Curator 等新 pipeline
- Forward 不 tie 任何 target、產的是通用 lemma、多 Goal 可援引

---

## 5. 驗證目標：Residue Theorem

### 為什麼選

- **有 Mathlib gap**：Mathlib 有 Cauchy integral 但缺一些 contour 操作的具名 lemma、剛好 Forward 補
- **層次清楚**：基礎 → 中間 → 最終、Forward 可分多輪逐步補
- **規模可控**：不是「證 Fermat」這種需要大量原創數學、是 Mathlib「再走一步就到」的水平
- **可驗證 Strategist 多種決策**：何時 InjectForward、何時投資新方向、何時放棄走偏 sub-goal

### 成功標誌

- `Problems/residue_thm/Root.lean` main proved、`#print axioms` 在白名單內
- 四 pipeline（Backward / Builder / Strategist / Forward）都有實際派遣紀錄
- Forward 至少貢獻 3 條 lemma 後被 main proof 引用
- Strategist 至少有一次 decision 不是「順照 BFS」（證明 meta 層有實際作用）

main 沒 proved 但 cycle 跑通、各 pipeline 行為符合 spec、Phase 2 仍算達成。

---

## 6. Open questions

1. **語意等價 dedupe 逃漏**：既有 `find_canonicals_batch` 擋句法等價（含 alpha / hyp-extension），但邏輯 rewrite / curry / 不同條件形式等語意等價會漏。強化 dedupe 是獨立大事、Phase 2 先不碰；短期靠 Strategist self-feedback 部分補洞。

---

## 7. 落地順序

1. Strategist + Forward prompt 草稿（先跟 user 對齊措辭、prompts/ 改動 discuss-first 規則）
2. DB schema migration + dispatcher 觸發邏輯（純程式）
3. residue_thm Problem 初始化（Manifest 預備）
4. 跑 Phase 2 第一次驗證、量觸發頻率與 Forward 命中率、calibrate `strategist.interval_min`
