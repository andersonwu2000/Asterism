# Librarian Cleanup — 把 Library 精修到 mathlib-PR-ready（設計手冊 v0.4）

操作 / 設計手冊。`docs/internal/`（gitignored）——會隨討論與實作 drift。
最後更新：2026-06-09。**dedup + P2（c2 證明簡化 + e docstring）+ P3-(2) 變數提取（e，un-∀ + 共用變數
hoist）已實作並接進 chain**（per-file dispatcher work-kind，P3-(2) e2e GREEN：normal_diagonalization +
polar_decomposition 各檔 #check gate 綠、兩題 Gate B PASSED）;**P3 分段是下一步**。設計 SoT = **§13**;§10/§11 為歷史脈絡。

> **一句話**：v0.3 把 Librarian 收斂成「忠實機械搬運（goal #1：能用）」並把「整理乾淨（goal #2：
> mathlib-PR-ready）」整段砍掉（見 `librarian_plan.md` §0/§4/§8）。v0.4 把 goal #2 重新設計加回——
> 不是把舊 cleanup 開關打開，而是重新組織成**分階段、各自 gate-verified、loop 到 fixpoint 的精修
> campaign**，並改變「什麼能進 Library」的門檻。

---

## 0. 目標與定位

- **目標**：把已證 problem 收成的 decl 整理到**社群會接受（mathlib-PR-ready）**的程度。涵蓋 decl 級、
  檔級、與 mathlib 規範對齊三個面向，無法單一階段處理 → 設計成**多階段、分批落地、逐步落實**。
- **定位**：Librarian 流程的**必要階段**（proof 完 + Manifest `library:true` 就跑，跟 inventory/classify/
  migrate 同一條鏈，非 operator 手動 campaign），對 staging 的收成跑；per-problem；可中斷續跑；
  **loop 到 fixpoint**（再跑一輪沒有任何 pass 產出改動才停）。
- **為什麼當初被砍**（不能重蹈）：(a) **順序死結**——改簽名要更新下游 call-site，但下游還沒落地；
  (b) **高 variance / 脆弱**——把昂貴脆弱的 goal #2 綁進主鏈拖垮便宜可靠的 goal #1。v0.4 用
  「全 migrate 後才精修 + cone re-gate（不靠固定順序保正確）」治 (a)、用「分級 gate + fixpoint +
  每 pass commit-or-rollback」治 (b)。

---

## 1. 曝光門檻（最硬的不變量）

**進 `Library/`（被 INDEX 列出、可被跨題 cite、A 的 reuse 池會看到）的硬門檻 = goal #1**：

1. 每個 decl `#print axioms` ⊆ whitelist（**公理檢查**）。
2. **Gate B**：從只 import Library 的探針一行**秒掉原始 root**（root re-derivation，Defs-free）。

**cleanliness（goal #2）不是曝光的硬門檻，是 best-effort**：

- cleanup **跑到哪算到哪**；卡住就**回退到最後一個可執行點**（= 最後一次 gate 全綠的 commit，
  我們每 pass commit-or-rollback，這個點免費就有）。
- 每個還沒做完的檔，**檔頭留顯眼 watermark**（見 §5），半乾淨狀態姑且曝光、姑且用著。
- **全階段過 → 清掉 watermark**。watermark 在 = 未完成；watermark 不在 = 真 mathlib-ready。

> 換句話說：goal #1 是「能不能進 Library」的硬 gate；goal #2 是「進來之後乾淨到哪」的 best-effort 標記。
> 非收斂的 decl 因此**不會卡死曝光**，只是帶個疤；A 可能 cite 到帶疤的 decl——沒問題，它是 gate 過的、
> 正確，只是還不漂亮。

---

## 2. 全流程 / staging 模型

```
 [problem root proved + integrity_verified=1 + Manifest library:true]
        │
        ▼  INVENTORY（縮到 reachable-from-root keepers，先跑——避免後面對 debris 白工）
        │
        ▼  PHASE 1 — strategist 抽象化 / 通用化 / factoring（建通用 G、重證；§7）
        │     rollback-safe：留原證明；新路把 root 重證到 integrity_verified 前，舊 goal 絕不 shelve
        │
        ▼  classify（語意分檔，沿用 v0.3）→ migrate（機械 relabel，整檔組裝，no LLM）
 STAGING（不在 Library/、不寫 INDEX、A 不引用）
        │
        ▼  PHASE 3+ — cleanup（§3–§7，綠 baseline 上、loop 到 fixpoint）
        │     先做 dedup（§7）；其他 cleanup（decl polish / file 結構 / 命名規範）之後慢慢加
        ▼  曝光門檻（硬，§1）：axiom + Gate B 秒掉 root
 LIBRARY/（promote + 寫 INDEX；未完成則檔頭留 watermark 標 cleanliness 程度）
```

「進 Library = goal #1 達標（axiom + Gate B）」；cleanliness 是 best-effort + watermark。migrate 的產出
落 staging、不直接曝光。**direction 3 骨架**：cleanup 在「先組裝、gate 綠」的 baseline 上逐 decl 精修
（peel out → 改 → re-gate → swap 或 revert），所以 staging 那層本身就是「最後可執行點」。

---

## 3. 安全地基：意義守恆 + 分級 gate

每個 cleanup 動作必須**意義守恆**，靠現成 oracle 守：Gate B（重推 root）、Gate D（def def-equiv）、
axiom whitelist、改檔後重建 affected cone（reverse-topo build）。**只要每 batch 收尾 gate 全綠，clean
可以多激進都行**——agent 怎麼簡化證明、怎麼重命名都無所謂，gate 抓任何漂移。這治掉 v0.2 cleanup 的高
variance：variance 只影響「改了哪些」，不影響正確性。

**gate 成本 = 改了什麼的函數**（不要一律 build cone）。transform → 最小充分 gate：

| 改動類型 | 最小充分驗證 |
|---|---|
| 只動註解 / docstring | **非-code-token diff**：剝掉 `--`、`/- -/`、`/-- -/` 後比對；code token 全同 → 不 build |
| 改證明 body、簽名不變 | **單檔 / decl-cone build**（dependents 不受影響） |
| 改簽名 / 命名 / 結構 | **cone re-gate**（reverse-topo） |

**批次**：同一個 decl 的「簡化證明 + 修 docstring + 刪 unused arg」併一個 pass、付一次最貴的那級 gate。
原則 = 同 blast-radius 的改動批在一起。

---

## 4. 組織形式：lifecycle-state 驅動的 work-kind + fixpoint

復用現有 chain 機制（`library_decls.lifecycle` + `_derive_librarian_work`）：cleanup 拆成數個 lifecycle
狀態 / work-kind，每個 pass = **選一個單位（decl 或檔）→ 小改 → §3 分級 re-gate → commit 或 rollback**，
**loop 到 fixpoint**。小步、可驗、可中斷續跑、天然分批。

### 兩軸框架

- **軸 1 — 檔內 / per-decl（decl-序遍歷）**：證明簡化、docstring、刪 unused arg、decl 改名、
  intra-file dedup、coverage 偵測。
- **軸 2 — 跨檔（topo 序）**：檔結構 / 分段 / 合併、共用變數提出、跨檔 dedup、跨檔引用修復（含 decl
  改名的 propagation）、檔註解。
- **拓樸 / decl 序當 batching 骨架**（build 攤銷 + 決定性遍歷），但**正確性不依賴順序**——靠 cone-regate
  + fixpoint。這正是治 v0.2 ordering deadlock 的關鍵。

### migrate 機械、cleanup 在綠 baseline 上做（direction 3）

migrate 維持**純機械整檔 relabel（no LLM、落 staging、可重現、錯誤率極低）**；所有 agentic 精修放到
「migrate 全部組裝、gate 綠」之後，逐 decl 在綠 baseline 上做（peel out → 改 → re-gate → swap 或 revert）。
理由：goal#1 先落袋、rewire-or-revert 有可 build 的 artifact 可驗、每 pass 便宜可退、staging 本身就是
「最後可執行點」。把 cleanup 塞回 migrate 會重蹈 v0.2「邊搬邊改」的脆弱。agentic 精修失敗 → 該 decl 維持
原樣（綠 baseline 上 = 安全 no-op）+ watermark。

---

## 5. Watermark（檔頭，機器可讀 + 人眼顯眼）

結構化檔頭註解，**一檔兩用**：給人看「別當這是 mathlib-ready」、給 campaign 看「下次從哪續」。範例：

```lean
-- ⚠ LIBRARY-CLEANUP: through=P2(decl polish); pending=P3,P4; stuck=foo_lemma(simp NF); 2026-06-07
```

- `through=` 已過的最後階段；`pending=` 還沒做的；`stuck=` 卡住的 decl + 原因。
- **全階段過 → 整行刪掉**（無 watermark = 真乾淨）。campaign resume 讀這行決定從哪續、跳過哪些 decl。

---

## 6. mathlib 規範：linter 是地板不是 oracle

社群規範**嚴於**內建 `#lint`：

- **linter（simpNF / unusedArguments / docBlame / …）= 便宜機械 pre-filter + 必過驗收地板**。
- **地板之上的對齊是 agentic 語意判斷**——命名美感、抽象選得對不對、golf、simp-normal、`variable` 用法…
  需餵一份**策劃過的社群規範參考**（mathlib naming/style 文件 + 自己歸納的 checklist），不能只丟 `#lint`。
- 這層注定 agentic、有 variance——靠 §3 分級 gate + linter 地板兜住正確性與「達標與否」。

---

## 7. Dedup（設計）

### 7.1 統一觀點：對排序 canonical 池做 redundancy 消除

「殺 mathlib 輪子」「Library 內去重」「同題內去重」**是同一件事**——「這個 decl 是不是已經有人有了？
有就 drop/cite/merge」。差別只在 canonical 來源。統一成一個機制、來源**排序**：

> **mathlib > 既有 Library（別題）> 同題其他 decl**

命中誰、survivor 就是誰。**池子** domain-scoped（`_eligible_library` 預篩可復用），**但測試是定義等價、
不是 A 的 apply-probe**：`apply @Y <;> assumption` 測「X 是 Y 的**推論**」——對 reuse 對、對 dedup 太鬆
（通用結論 lemma 是一堆東西的推論，jordan 實測 87/93 假命中）。正解是 term-mode 探針
`theorem : <X 的 ∀-type> := @Y`（只有 `Y : X.type` defeq 才 typecheck），實作 `dedup.py:batch_defeq`。

### 7.2 兩種模式

- **exact / near-dup**：X ≡ Y 定義等價 → 機械 drop；近重複（非 defeq、可一行導出）→ LLM 補一行橋。量大。
  → **PHASE 3 cleanup**（已實作，§10）。
- **factor-general**：X、Y 結構相似但誰都不蓋誰 → 抽通用 G、各自導出。語意、需**重證**、稀少但高價值。
  → **PHASE 1（strategist，proof 層）**，重證用 inject 是現成機械（未實作，§12）。

### 7.3 安全不變量

- **rewire-or-revert**：任何 drop/merge（X→Y）只在 (a) 機械改寫**所有** X 引用成 Y、(b) cone re-gate 過
  才落地；**任一不過 → 不殺、保留 X**。「殺出補不上的洞」結構上不會發生。激進度由「引用能不能安全 rewire」
  自動限幅，不靠調參數猜——直接治「殺太多補不上 / 殺太少不達標」。
- **決定性 survivor 規則**（治並行 race、保可重現）：X≡Y 時固定規則選誰活（草案：能 cite mathlib >
  離 root 近 > 證明短 > 名字更標準；現用「短名優先」）。**A-fix（`b131172`）後降為 cosmetic**：same-file
  pair 信 marker 指定的 survivor、cross-file 才用此規則做並行決定性 → 只影響「哪個名字活」、不影響 recall。
- **PHASE 1 rollback-safe**：留原證明；新路（inject）把 root 重證到 `integrity_verified` 前，舊 goal
  **絕不 shelve**；任何時刻 root 保持綠。
- **PHASE 3 decline = 安全 no-op**：綠 baseline 上「這個 decl 不需要 dedup」就維持原樣、**無洞**。
- **復原**：事後發現某 drop 該留 → 走現成 un-drop / needs-upstream（#85）。

### 7.4 兩軸提醒

dedup **偵測在軸 1**（per-decl / 看整檔 set——一條 decl 可能跟較晚的重複，流式會漏）；**rewire 在軸 2**
（殺 X 要把別檔消費者 rewire 到 canonical）。所以 dedup = 「偵測軸 1 / rewire 軸 2」拆兩半。

---

## 8. cleanup 內的 phase 串（PHASE 3+；全鏈見 §2）

```
STAGING（migrate 機械產出、gate 綠 = baseline）
  → P1 redundancy（§7，已實作）：對 ranked 池 mathlib>Library>siblings 做 dedup
        （殺 mathlib 輪子 + cite 也在這裡，§7.1 統一）。
  ── 以下「之後慢慢加」──
  → P2 decl polish：簡化證明 / docstring / 刪 unused arg（automation 薄包裝 inline 在此）
  → P3 file 結構：分段 / 共用變數提出 / 合併檔 / 檔註解（cone re-gate；軸 2）
  → P4 命名 + 規範對齊：agentic 語意對齊 + 引用修復、linter 地板（§6）
  → 驗收：linter 全綠 + axiom + Gate B → promote staging→Library + 寫 INDEX + 清 watermark
全程 Librarian 階段、per-problem、可中斷續跑、loop 到 fixpoint。
factor-general 不在這串——它在 PHASE 1（strategist，§7.2），migrate 之前。
```

排序理由：**先縮集合、改引用的擺前面集中處理**——P1 redundancy 先縮 decl 集合，再在 survivors 上
per-decl 精修（P2）、檔結構（P3）、命名最後一次到位（P4），避免反覆 re-touch。
**進度（2026-06-10 實作收斂後的 stage 對照）：per-file flow =
`dedup(機械) → simplify(per-decl) → unused_args(機械) → strip_comments(機械) → polish(agentic 整檔,
型別不變 gate：變數提取+docstring+module docstring+style+清警告,supersede 舊 variables/docstring 兩
stage) → decide(agentic propose→機械 apply：P4 命名對齊 + `import Mathlib` 傘換精準 imports,降級階梯
= imports 紅不連坐 rename,supersede 舊 rename stage) → bridge/Gate B`。
P1 ✅ P2 ✅ P3(變數提取/分段→polish)✅ P4 命名(rename 2 題 e2e GREEN→併入 decide)✅;
P3 合併檔 + audit stage(語意 idiom,§mathlib_conventions §8)= 待做。**

---

## 9. 與其他工作的關係

- **取代** `librarian_plan.md` §4 對 cleanup re-add 的草稿。
- **與 A（cross-problem Library reuse，commit 5afa013）的綜效**：乾淨、標準命名、去重後的 Library 讓
  A 的 apply-probe 命中更多。quality 工作自動回饋 reuse。
- **#93**（機械 isDefEq dedup）= §7 dedup 的保守地板；**#94**（cleanup / mathlib-PR pass）= 本文件整體。

---

## 10. 實作現況（standalone dedup 引擎）

dedup 引擎已實作、**standalone**（`python -m Tooling.quality.librarian.dedup <problem>`，DB-free、不經
dispatcher）。流程 = **per-file audit marker → 機械 gate**：

- **marker（`--audit`，推薦）**：一檔一 agent（prompt `librarian/dedup_audit.md`），對**每個 decl** 給
  verdict `keep/drop/cite-mathlib/cite-library/merge`；context 餵該檔 decl 的 statement **+ proof**
  （薄包裝可見）、同題 siblings、token-nearest pool shortlist；mathlib 走 loogle 不 dump。marking **平行**
  （`--jobs N`，預設 4）；gate sequential。
  - 取代早期「平面單呼叫 marker」（舊 `--llm`/`--mark`,**已退役 `68bb206`**）：平面版注意力分散、只給簽名
    → 漏輪子。per-file audit 逐 decl 覆蓋、recall 高（jordan 5 bridge vs 平面 1、eckart 10 vs 6）。
  - `find_thin_wrappers`（`--thin`）：機械讀 proof 抓一行薄證明——**delegating**（`by exact/apply/simpa
    using <L>` / term head → 有 twin → dedup 目標）vs **automation**（`by simp/norm_num/grind` → 無單一
    twin → inline 候選 = P2，非 dedup）。
- **gate（`apply_llm_pairs` + bridger）**：verdict → (x,y) pair → ranked-pool isDefEq 探針（`batch_defeq`）：
  - exact-defeq → **drop + rewire**（rewire-or-revert，重建問題模組為閘）。
  - defeq 但 survivor 是薄包裝、其證明引用被丟者 → **wrapper-merge**（把真證明搬上 survivor、drop 包裝）。
  - 非 defeq 但可一行導出 → **LLM bridge**（塌縮證明成 `:= <bridge>` 引 twin、保留 statement、消費者不動）。
  - y 不在 pool → 當 **mathlib**（`_resolve_y`，module='' 哨兵、不 import、永遠 survivor、不 merge）。
- **安全**：每筆改動 build-gated；`_external_consumer` 守門（有跨題消費者的 decl 不丟，見 §11 跨題）。
- **實證**：courant/sylvester/eckart/jordan 多題 e2e、git/備份還原；抓到 mathlib 輪子
  （`n_distrib_smul_sum→map_sum`、`range_restrict_nilpotent`、`maxgen_eigenspace_invariant→
  mapsTo_maxGenEigenspace_of_comm`）。但 **lemma 層 mathlib 輪子罕見**（LA Library 多是領域組合）。
- 單元測試 `tests/test_librarian_dedup.py`（全綠）。逐 commit 演進看 git log；本節只記當前形狀。

---

## 11. Chain 整合設計（✅ 已實作 = §13；本節為**歷史脈絡**，live 形狀見 §13 + STATUS）

把 §10 的 standalone 引擎接進 Librarian chain，成為**必要階段**：proof 完 + Manifest `library:true` 就跑，
跟 inventory/classify/migrate 同鏈（非 operator opt-in campaign）。`library_decls.lifecycle` CHECK 已預留
`cleaned`/`dropped`/`cited`（v0.3 砍時留著），**不需 migration**。

**鏈位置 + staging/promote**：
```
… migrate（機械、整檔組裝）→ bridge → INDEX（staging，未 promote）
   → cleanup-dedup（本引擎）→ 曝光 gate（axiom + Gate B 秒 root）→ promote（清 watermark）
```
migrate 後 Library 進 **staging（未進 Library/、A 不引用）**；cleanup 在 staging 上做；整題過曝光 gate 才
promote。舊的 `candidate` dedup slot 維持 no-op（keepall）。

**處理模型**（⚠️ per-decl cone 版已被 **§13 定稿(per-decl staged agentic pipeline)** supersede；下段保留為脈絡）：
- **檔層級**：依 import-DAG **拓樸序（bottom-up：依賴先、消費者後）分派，獨立檔並行**；並行單位 =
  slot/pipeline，數量受 `dispatch.pool` 控（復用 #92 DAG 排程 + proving 的 bfs-refill 模式）。
- **檔內**：decl **逐筆 sequential** apply+gate——一筆改動（drop/bridge/merge）→ **cone build（decl +
  消費者，非整題）** → 過則替換進組裝檔；否則機械改動 revert/decline、agentic bridge 把 lake error 餵回
  retry（builder/migrate 式 session-retry）。
- **可續跑**：verdict / 進度寫 DB（`library_decls` verdict+lifecycle）+ 檔頭 watermark；重入接著跑、
  不重 audit。

**跨題（暫不做，future）**：被 drop 的 decl 若被別題引用，`_external_consumer` 現在 **skip**（不丟、留著）。
設計上不需擔心——**只有 cleanup 完才 promote 進 Library 的東西會被別題引用**，所以別題引用的都是已清穩定的
decl，一題 cleanup 不該需要動別題。全跨題 rewire（cone 擴到全 Library 引用閉包 + 跨題原子 revert）列
future，有技術需要再做。

**規模**：多步工程（dispatcher chain 延長 + staging/promote + cone-build gate + 可續跑）。建議分階段，
standalone 引擎是現成的 cleanup 核心，整合是把它接進 chain。

### 實作狀態（2026-06-08）

- **Phase 1 ✅**（`aea3c5e`）：cleanup work-kind 進 chain。`_derive_librarian_work` migrated→cleanup→
  cleaned→bridge；`run_librarian` 路由 + `_run_cleanup`（跑 `run_file_audit_dedup(apply=True, scope_index=DB)`，
  推進 lifecycle：engine-dropped→`dropped`、survivor→`cleaned`）；engine 加 `scope_index`（in-chain 從 DB
  給 scope、pool 仍 INDEX）。無 schema migration。
- **Phase 2 ✅**：曝光 gate post-cleanup = 設計即滿足（cleanup 在 bridge 前；bridge Gate B 對 post-cleanup
  root cone 做 build + axiom）。
- **Phase 3（option 1）部分 ✅**（`dbccae0`）：**bridges** 走 option-1 gate——`_build_decl_isolated`
  （per-decl 隔離 probe：`theorem _cleanup_probe <binders> : <concl> := <bridge>`，import 該 module +
  open namespace，**binder 留 header 不 ∀-collapse**——踩過的 bug）+ apply_bridge per-file build（只建該
  module，sig-preserving 消費者不動）。**drops 仍 whole-problem rebuild**。

---

## 12. Open / future

- **chain 整合 3c = 實作 §13 定稿形狀**（per-decl staged agentic pipeline，E2+B）。分兩階段:3c-1（序列、
  驗模型正確性）→ 3c-2（E2 lift + 檔間並行 + 跨 process splice 鎖）。細節見 §13。
- **PHASE 1 strategist factor-general**：jordan 評估只 **1 個低-ROI cluster**（「LI-子家族 ⟹ 係數消去」：
  `d_coeff_vanish`/`chain_bottom_coeffs_of_sum_zero`/`comp_coeffs_of_mem_range`/`chain_bottoms_li` 共用
  `basis.linearIndependent.comp → .map' 抬進 W → Fintype.linearIndependent_iff` 骨架，~30 行）。其餘相似
  家族(`*_strong`/block_enum/chain_partition)要嘛已抽過、要嘛單次 pipeline。重型 strategist factor 機制
  ROI 偏低；單點可當輕量 cleanup 手做。trigger / 與 decision-kinds 接法 / rollback 狀態機待設計。
- **P2 ✅ 完成**（`355fdd7`，2026-06-09）：proof 簡化（marked-only per-decl）+ docstring（whole-file）。**P3–P4 待做**
  （§8）：file 結構（分段 / 共用變數提出〔需 retry〕）、命名 / 規範對齊。下個 session 從 P3 起。
- **verdict-native gate（optional polish，correctness 已 secured）**：chain 的 marker 早是 verdict-per-decl
  （`dedup_audit.md`→verdicts.json），但底層 gate 仍 pair-based（v1a 留的），`_audit_pairs` 是 lossy adapter。
  改成 gate 直接吃 verdict（survivor=`name`、kind 保留、batch_defeq 仍當驗證）可退役 `_audit_pairs`。Finding A
  已用「same-file 信 marker / cross-file `_survivor` 決定性」補好正確性（`b131172`），故此重構純整潔、不急。
  legacy flat pair-marker（`dedup.md`/`run_llm_dedup`/`mark_context`/`parse_dedup_pairs`/--llm/--mark）**已退役
  （`68bb206`）**；其餘 legacy `__main__` CLI（--audit/--pairs/--thin/campaign）若不再要可再退。
- **#3 survivor tie-break 定案**：A-fix 後 `_survivor` 只決定「哪個名字活」（cosmetic），不影響 recall。
- **P2–P4 cleanup**（§8）：decl polish（automation 薄包裝 inline 在此）、file 結構、命名 / 規範對齊。
- **scaling 預篩**（Library 變大）：audit context 餵整池 → IDF/embedding top-K；`_external_consumer` 全庫
  rglob（O(庫×候選））→ 一次性反向 consumer 索引。根本解 = harvest-時增量（chain 整合）而非全庫重掃。

---

## 13. cleanup 引擎形狀（定稿 2026-06-08）：per-decl staged agentic pipeline

> 框架層 cleanup 的目標形狀（user 對齊定稿）。**dedup 是其中第一個 active 子階段**；decl-cleanup /
> file-cleanup 階段先當 **no-op hook**，之後的 cleanup 工作（§8 P2–P4）往這個 shape 裡塞。supersede §11
> 「處理模型」的 per-decl cone 版。實作 = 3c（見本節末分階段）。

### 原則
- cleanup = **per-file work-kind**；dispatcher 依 import-DAG **拓樸序（bottom-up：依賴先、消費者後）分派**，
  獨立檔**並行**（並行單位 = slot/pipeline、受 `dispatch.pool` 控、復用 #92 DAG 排程）= **E2**。
- 檔內 decl **依序、單 decl 隔離**（同檔 decl 間有相依，不並行）。
- **marking 維持 per-file 批次前置**（一檔一 agent 出全檔 verdict；無 race、順序無關）；per-decl 迴圈只**消費**
  marks。只有 bridge / polish 才 spawn per-decl LLM；**exact-defeq drop 仍走機械**（可證相等 →
  deterministic rewire，免 LLM、零不確定性）。
- **兩個 marker（per-file、並行）**：dedup-marker（現成 `dedup_audit.md`，要 pool shortlist context）+
  cleanup-marker（新，只看 proof 本身、判哪些值得 proof 簡化）。context 需求不同 → 分開，dedup prompt 不動。
- **operation 的形狀按成本分兩類**（user 對齊定稿 2026-06-08）：
  - **proof 簡化 = marked-only、per-decl session-retry**（單顆 proof 重寫太貴 → marker 先篩，只對標記的付）。
  - **docstring（decl + file 註解）= 全檔一次 pass**（便宜、不需 marker；safety = code-token 不變 gate）→
    放 (e) file-cleanup 階段。

### 執行流程（a–e；dispatcher 單元 = per-file，檔內 per-decl）
> 標記法:`a–e` = runtime pipeline 步驟（流程「形狀」）；`c1/c2/c3` = step c 底下的轉換子階段（會長,
> 故編號）。**勿與 `3c-1/3c-2/3c-3` 混淆——那是實施里程碑（見本節末分階段），不是 runtime 步驟。**

對拓樸序中每個檔、檔內每個 decl（依序）：
- **a. 排序**：problem 依檔案拓樸序（bottom-up：依賴先、消費者後）**並行**；檔內依 decl 序、單 decl 隔離、
  依序執行。正確性靠 cone-regate 不靠順序,topo 只攤銷 build（治 v0.2 ordering deadlock）。
- **b. 標記（per-file 並行）**：一檔一 agent 出全檔 verdict（無 race、順序無關）;per-decl 迴圈只**消費** marks。
  兩個 marker context 需求不同 → 分開:**dedup-marker**（現成 `dedup_audit.md`,要 pool shortlist）+
  **cleanup-marker**（`cleanup_mark.md`,只看 proof 判哪些值得簡化）。
- **c. decl-cleanup（逐 decl 消費 marks）**：每個子階段都過「**隔離 build + 驗公理**」gate——對隔離檔
  （`_build_decl_isolated`:`theorem _probe <binders> : concl := proof`,import 該 module + open namespace,
  **binder 留 header 不 ∀-collapse**——踩過的 bug）build + axiom;過了才**機械併回整合檔**,整合檔只收已驗證
  decl,失敗必歸屬當下 decl → retry、無追蹤問題。子階段（**c1 整檔批次、c2 起 per-decl sweep,分開跑、gate
  不同 → 不混進單一 branch**）:
  - **c1 — 機械 dedup（現成）**：incoming rename + 本檔 drop/同檔 merge/bridge。**exact-defeq drop 不 build**
    （defeq-safe）;bridge 走上述隔離 build。= `_cleanup_one_file` 現狀,整檔批次。
  - **c2 — per-decl 證明簡化（P2 ✅）**：依 decl 序、**僅 cleanup-marked 的 survivor**。優先序
    **drop > bridge > simplify**（dropped 沒了、bridged 已最簡 → 跳過）。每顆:隔離 → spawn 簡化 → 隔離 build
    → 過則機械 splice、不過餵 lake error **session-retry**（migrate 式）→ 到 threshold **回退原 decl**
    （checkpoint = 該 decl 原文,decl-isolated、零風險）。保簽名 → 不觸發 d。
  - **c3 —（未來）**：刪 unused arg / decl 改名等 per-decl 轉換;改名/刪參會變簽名 → 觸發 d。
- **d. 消費者改寫（僅當簽名有變,如 drop / sig-changing polish）**：消費者**依檔分組**、deferred 自套
  （dedup = 機械 token-replace;sig 變 = agentic 適配）。c2 證明簡化保簽名 → **不觸發**；P3 共用變數提出、
  c3 改名等才走。
- **e. file-cleanup（該檔所有 decl 清完後）**：LLM 對整檔做 file 級 cleanup → build → retry。e 內順序
  **變數提取 → docstring**（先定結構再寫註解,免 re-touch）。**失敗 session-retry → 到 threshold 回退整檔**
  （checkpoint = 原檔）。各 pass 的 safety gate 按改了什麼挑:
  - **變數提取（P3-(2) ✅,prompt `variable_extract.md`）**：un-∀-prenex + 把全檔共用 binder hoist 到檔頭
    `variable`,改 code 故非 code-token gate。safety = **#check 簽名快照**(`lean --json` 印每 decl 仰展開
    全顯式型別,改前/改後比對,任一變 → retry;`@` 攤開 implicit/instance、`u_n` 正規化)。一次 build 兼
    proof gate + 簽名擷取,**不 build 消費者**(Lean 算 `variable` inclusion、我們只比答案)。機械預篩:無
    ∀-prenex 又無共用 binder → 跳。e2e GREEN(7/7 檔 extracted、兩題 Gate B PASSED)。
  - **docstring（P2 ✅）**：code-token 不變 gate（剝 `--`/`/- -/`/`/-- -/` 後 code token 全同,擋盲改污染 #91）+ build。
  - **P3 分段 / P4 命名 / 合併**(待做)也落 e,**同樣需 retry**（user 提醒:共用變數提出 step 必帶 retry）。

### build 階層
per-decl 隔離(c) → per-consumer-group 隔離(d) → **per-file(e，P2 起開:docstring/結構非 defeq、必建 + retry)** →
**Gate B（全題、axiom + 秒 root、bridge 階段、已有）= 曝光硬門檻**。

### 並行與寫入安全（E2，deferred-rewire——免鎖）
跨 process 鎖被 **deferred-rewire** 取代（更乾淨、天然 race-free）:
- **不變式 = 每個檔恰好被自己的 per-file worker 寫一次**。drop X 時 worker 只改 X 檔自己 + **把 rename
  `X→Y` 記進 DB**（= `library_decls` dropped verdict 的 `citation`，無需新表）;**不碰消費者檔**。
- 消費者檔（都是 X 的依賴者、topo 在後）輪到自己 worker 時,**先套用 DB 累積的所有 pending rename 再 cleanup**。
  topo 的 indegree 保證消費者跑前其所有依賴已完成 → 相關 rename 都記好。
- **匯流安全**:A 引 B、C 且 B、C 都變 → A 只被自己 worker 寫一次、一次套齊 `B→B'`+`C→C'`(B、C worker 不碰
  A)。rename 經 `_resolve_drop_chains` 指向最終 survivor → 不相交、可交換。stale olean 對 survivor 仍解析。
- LLM 隔離工作 + marking 並行;唯一「跨檔效應」(rename)走 DB 非並發寫 → 無鎖、無 race。
- **邊角:wrapper-merge 把 X 證明搬到別檔的 Y** = 跨檔寫。典型 merge 同檔(wrapper+real);跨檔 merge 先
  defer（記給 Y 檔 worker 套）或 skip（留 near）。

### decline hooks（細節稍後談）
- (b/c) dedup 無事可做 → 跳 decl-cleanup（部分已實現:near 空則不 bridge）。
- (d/e) 過不了 → 允許 LLM decline 回上一步。先把 hook 留好。

### 分階段實施（每階段過 2 committed-clean 題才進）
- **3c-1（模型正確性，序列）**：把 cleanup 重構成 per-file（topo **序列**）+ per-decl staged 迴圈（a–e，
  decl-cleanup / file-cleanup no-op）+ 消費者 isolate-then-splice（in-process 鎖）。**不上 dispatcher、不並行**，
  純驗 a–e 的 per-decl 模型在 2 題正確。復用 3b 的 `_build_decl_isolated` + 機械 primitives。
- **3c-2（E2 lift + 並行，deferred-rewire）**：cleanup → per-file **dispatcher work-kind**（鏡像 migrate 的
  `next_migrate_file` 派工）+ topo pool 排程(#92) + **DB rename-map + 消費者自套（免鎖）**。給「單一大題內
  檔間並行」+ 框架對齊。3c-1 的 per-decl 邏輯沿用，只把「整問題序列」拆成「per-file（每 worker 只寫自己檔、
  先套 pending rename）」。
- **3c-3（P2 cleanup ✅ 完成,commit `355fdd7`,e2e GREEN）**：填 (e)/(c) 的 agentic hook。**兩條依序**:
  - **P2a docstring（(e) file-cleanup,先做)**：全檔一次 → code-token 不變 gate + build + session-retry → 回退整檔。
    新 prompt `docstring.md`。不需 marker、不需 per-decl session-retry → 最便宜,先驗 (e) 階段 + retry 機制。
  - **P2b proof 簡化（(c) decl-cleanup,後做)**：cleanup-marker（新 `cleanup_mark.md`）+ per-decl session-retry
    （新 `decl_simplify.md`）。優先序 drop>bridge>simplify。重在 marker 篩 + migrate 式 retry。
  - per-file build (e) flag 對 P2 **開**（非 defeq、必建）;`_build_file_copy_isolated` 已留著。

### 實作狀態
- **3b**（`dbccae0`）：bridge 的 per-decl 隔離 build（`_build_decl_isolated`，binder 留 header）= (c) 雛形。
- **Phase 1**（`aea3c5e`）：cleanup work-kind 進 chain（per-problem 粒度）= 3c-2 細化成 per-file 的起點。
- **3c-1 ✅ 完成**（`2575bd6` primitives → `3986241` 引擎 → `09e7fc6` merge+接線）:
  - primitives:`_file_topo_order`（bottom-up,inline，+ unit tests）、`_lake_check`（共用 isolate-typecheck）、
    `_build_file_copy_isolated`（整檔副本 typecheck,(d) 用）。
  - `run_staged_cleanup`(序列):mark（`_collect_marked_pairs` 共用）→ `_classify_pairs`（drop/bridge/skip +
    `_resolve_drop_chains` 鏈解析）→ topo per-file `_cleanup_one_file`（deferred-rewire:套 incoming rename +
    本檔 drop/同檔 merge/bridge,只寫本檔,drops 回傳累積進 rename_map 給後續消費者自套）。CLI `--staged`。
  - `_run_cleanup` 已改呼叫 `run_staged_cleanup`(`3986241`→deferred 重構同 commit 系列)。
  - 驗證:courant 3 drop / eckart 8 drop + bridge,兩題 post-staged build **GREEN**、git 還原乾淨。
  - **無 per-file build(skip-(e),defeq-safe)**;backstop = bridge Gate B(in-chain)/ 手動 build(CLI)。
- **效能(`1fb5476` skip-build+O1 → `6a39b48` O4,measured)**:每題從 ~7-9 分 → ~5 分。phase breakdown
  (courant):`mark=196s classify=21s bridge-propose=50s`。三個 lake 殺手已解——per-file build(跳)、
  pre-flight 冗餘 24s(**O1** `_missing_oleans`:olean 存在就跳)、**classify 的 `_external_consumer` 全庫
  rglob(O4 `_nonscope_library_texts`:corpus 讀一次,240s→21s,最大隱藏殺手)**。**lake 已非瓶頸**;
  剩餘 = LLM agent(mark + bridge-propose)=不可壓縮的模型 latency,只能靠並行(3c-2)攤。`[staged-timing]`
  log 已內建。
- **warm worker(gateway)判決**:擱置。hot ~4s 只在「imports 不變只換 body」;cleanup 每 check imports 不同
  → cold env-rebuild ~20s(=#108)。且 lake 已非瓶頸,CP 值低。(成本模型讀 code+#108 推,未重測。)
- **3c-2c ✅ 接線實作 + 全單元測(2026-06-08 晚;e2e pending)**:cleanup 升成 per-file **dispatcher work-kind**
  (鏡像 migrate)。落地:`ready_cleanup_files`(仿 `ready_file_work`,deps `cleaned`/`dropped` 才 ready,fully-dropped
  檔算 done)、`file_work_kind` cleanup 分支(classified→migrate / migrated→cleanup / else None)、`file_dependency_graph`
  加 `lifecycles` 參數(cleanup 用 `(migrated,cleaned,dropped)` 保 import edge 穩定)、`_run_cleanup(target_file)`
  per-file(DB 撈 prior_renames→`run_staged_cleanup_file`→drops 寫 DB `set_library_verdict drop`+citation、survivors
  `mark_library_cleaned`;helper `_advance_cleanup_decls`/`_cleanup_scope_index`)、dispatcher `_derive`/`_librarian_refill`
  (migrate+cleanup 併 per-file enqueue 分支)/`_run_pipeline`(plain-row null cleanup)路由。full suite 1569 passed。
  **live e2e ✅ GREEN(full daemon,2 題)**:courant(3 drop+4 bridge→35 cleaned/3 dropped)、eckart(9 drop+2 bridge
  →28 cleaned/9 dropped),per-file dispatch + bottom-up topo + 跨檔 deferred-rewire(DB prior_renames)+ bridge
  **Gate B PASSED** 全驗,exit 0、git/DB 還原乾淨。**已 commit `9965912`**(4 檔:dispatcher.py/librarian.py + 2 test)。
- **3c-2 設計準則(P2-aware 通用 shell;P2 緊接著做)**:per-file dispatcher work-kind + topo pool 排程 +
  **deferred-rewire(DB rename-map,免鎖)**。目的=攤平 marking LLM latency(跨檔 + 跨題)+ **當 P2 的地基**。準則:
  - **per-file 入口做成通用 stage 結構**(不為 dedup 特調,P2 填 hook 不 refit):
    `[dedup stage:機械] → [decl-cleanup stage:P2 agentic,現 no-op] → [per-file build (e)]`。
  - **per-file build (e) = per-stage flag**:dedup **off**(defeq-safe),P2 **on**(非 defeq 必建);
    `_build_file_copy_isolated` 留著給 P2。
  - **deferred-rewire 是 dedup+P2 共用消費者模型**:每檔只寫自己、消費者輪到時自套——dedup=機械 self-apply,
    P2(sig 變)=**agentic self-apply**(消費者 worker LLM 適配),兩者都免跨檔寫 race。
  - **survivor-guard(不准 drop 已是別人 survivor 的 decl,防跨檔鏈)只掛 dedup stage**,不污染通用 shell。
  - 3c-2 不為 dedup 速度微優化(已快);職責=排程 shell + 跨題 + pool 控 + 乾淨 P2 hooks,`_cleanup_one_file`
    保持簡單。dedup 也走此 shell(不留 serial/dispatched 兩條路)。
- **survivor tie-break** 定案（§7.3 草案）。**A-fix 後僅 cosmetic**（決定哪名字活、不影響 recall）→ 緩。
- ~~**latent bug**：`dedupe._conclusion_of_signature` LAST-colon 切錯（同 `_to_forall_form`）~~ **✅ 已修**：
  把 canonical FIRST-depth-0-colon splitter `_type_colon_pos`（含 `⦃⦄`）放進 lower 的 `dedupe.py`，
  `_to_forall_form`/`_conclusion_of_signature` 改用它,`librarian.dedup` 也 alias 同一個（單一實作）。
  A 的 token 預篩不再 mangle ∃/∀/fun 結論。加了 ∃-conclusion 回歸測試（test_dedupe.py）。
- **規範參考 / mathlib 搜尋**：策劃社群規範 checklist（P4）、loogle 在 sandbox（`Tooling.knowledge.loogle`，
  已驗可用）。
