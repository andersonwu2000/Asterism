# Asterism v2 — Current Status

更新於 2026-05-05（thinking-budget cap 後）。HEAD `8f0d2b3`，**596 unit tests + 1 skipped green**。

## 下個 session 接手要做的事

Daemon 已停。下一步：**重跑 SG 驗證 thinking budget cap 效果**（commit `8f0d2b3`）。當前 SG DB 是上一輪的中斷狀態（root attempting, 7 sub-goals proved, g5 卡 Kelly contradiction）。建議**完全 reset**從零跑乾淨 baseline。

```bash
cd D:/Asterism
rm -f asterism.db
rm -rf .attempts/* Problems/sylvester_gallai/.drafts/*.md
python -m Tooling.cli init sylvester_gallai
ASTERISM_BUDGET_SEC=21600 python -m Tooling.cli run  # 6hr (跟 GitHub baseline 對齊)
```

**核心測試點：thinking cap 是否解 dive 問題**。對比舊資料：
- **舊（high adaptive thinking）**：74% Backward spawn dive（30-40K char thinking, 0 writes），SG g4/g8/g10 都死循環
- **新（10K token cap @ 1K/min）**：理論上 dive 觸頂被截斷、agent 強制進寫作模式

健康訊號：
- Backward spawn 的 thinking 不再超過 10K tokens（看 `~/.claude/projects/D--Asterism-Problems-sylvester-gallai/<sid>.jsonl` 的 thinking event size）
- dive(0 writes) ratio 從 74% 降到顯著低
- root proved 達成（這次未達；歷史只有 cantor ~4hr 達成過）

如果 thinking cap 仍解不了：
- 先看 jsonl thinking 是否真的 capped 在 10K（驗證 env 注入有效）
- 如果 cap 生效但 agent 寫不出檔，考慮再降到 5K-7K
- 如果 cap 沒生效（thinking 仍 > 10K），表示 `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` 沒被尊重，需 web research / 看 claude CLI 版本

## 本 session（2026-05-04 ~ 05-05）改動鏈

按 commit 順序：

1. `c6a2117` — **Backward prompt 5 個 skeleton**（exists+property / adapter+main / case dispatch / linear pipeline / induction+step）+ postmortem 加 alternative direction
2. `75f9deb` — **Sub-goal Defs auto-import** — `_ensure_imports_subgoal` 自動加 `import Problems/<p>/Defs`
3. `e9cbdd7` — **Infeasibility escape channel** + TACTIC_TRY 補 `assumption/tauto/exact?` + 刪 `difficulty>=4` hard gate
4. `c63e149` — **entry_kind directive** — Backward 為每個 sub-goal 標 Builder/Backward
5. `234de10` — **刪數字 difficulty** — Manifest `## Entry kind: Builder|Backward`，schema drop 欄位
6. `30392d2` — Backward prompt Rules 合併 stay-abstract directive
7. `9c7fc68` then `b117620` — **two-phase commit-phase 加了又回退**（實證 0% 救活，Sonnet thinking 一旦開始無法中斷）
8. `b117620` — `_safe_glob` 防 Windows reserved-char filename（agent 寫 `won_exact?.lean` 案例）
9. `ab03522` — Manifest `## Tactical` / `## Mathlib hints` → 統一 `## Lemma hints`
10. `8f0d2b3` — **thinking budget cap 1K tokens/min**（核心修復！env `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1` + `MAX_THINKING_TOKENS`）

關鍵實證：
- thinking dive 統計（148 個 spawn）：dive median 9K tokens, successful median 3.7K — 10K cap 是邊界
- two-phase commit-phase 失敗：session jsonl 顯示 commit prompt 後 agent 完全沒回應 → Sonnet thinking block 是 atomic
- entry_kind directive：之前 g422/g423 被無條件先 Builder 浪費，新機制讓 Backward 預判跳過 Builder
- infeasibility escape：g363 實證一次 spawn 內構造反例 + escape，省 SHELVE_THRESHOLD-1 次 timeout

## 最近批次（2026-05-04）

按時間倒序，三批改動：

**F55 redesign + F56**（commit `27d46bb`）— 改框架對失敗 spawn 的處理：
- F55 棄「邊寫邊存 PROPOSAL.md」改用「timeout 後 postmortem spawn 寫 _progress.md」。主任務不再要 agent 維護 deliverable，partial 從 deliverable 解耦成獨立側通道。
- F56 砍 worker_kind="Verify"。strategy 驗證改成 dispatcher tick 末端的 housekeeping 步驟（純框架、無 LLM、不佔 worker pool）。F41 LLM 修復同步取消（26 verify 0 觸發）。
- 兩件事一起做，因為 timeout 處理 + verify 收尾都是「失敗/收尾路徑的清理」性質的工作。

**M3**（commit `d045e15`）— `--add-dir <packages>` 修復 mathlib Grep 被拒問題。M1 加寬 allowlist 但仍有 75 次 Grep 拒絕，根因是 F44 narrowing cwd 後，claude permission 把 cwd subtree ∪ --add-dir 當隱式信任邊界，allowlist 被忽略。加 packages 進 add-dir 修。

**docs**（commit `919b1a8`）— `docs/data-flow.md` 新檔（概念敘事、agent 與框架資料流）；`architecture.md` v2.5 → v2.6 反映 F55+F56。

## Proved problems

| Problem | Prover | Wall-clock | Axioms |
|---|---|---|---|
| compactness | Opus | ~25 min | propext, Classical.choice, Quot.sound |
| compactness | Sonnet | ~60 min | 同上 |
| gen_generates | Sonnet | ~30 min | propext, Quot.sound |
| inner_zero_iff_smul | Sonnet | ~21 min | std 3 |
| proj_nonexpansive | Sonnet | ~58 min | std 3 |
| **cantor_xi_measure** | Sonnet | **~4 hr**（含 90min budget exit + 重啟）| std 3 |

cantor 是當前最大 sample（50 goals、depth 4、18 verify）。F55+F56 改動後尚未跑過完整題目 — SG 是首次驗證。

## 信號監控（每次 run 後檢查）

| 信號 | 期望 | 觸發來源 |
|---|---|---|
| `naming_violation` | 0 | F52 + F53/A |
| `patch_signature_mismatch` | 0 | F52 |
| Mathlib Grep denied | 0 | M1 + M3 |
| Cross-Problem read | 0 | F44 sandbox |
| `spawn_fast_fail` | 0（除非 quota）| F46 |
| 新訊號：postmortem `_progress.md` 寫入 | timeout 時寫一次、success 時清掉 | F55 |
| 新訊號：verify housekeeping promote | 每 strategy 一次、可鏈式 | F56 |

## 砍掉但留參考的舊機制

- **F40** Two-phase Builder（commit `2b6ff1a` revert at `232a3e0`）— Phase A 寫 PROPOSAL、Phase B 寫 patch。Haiku 實證證明瓶頸在 patch 品質不在 deliverable miss。除非新 model 失敗模式換成 deliverable miss，不重做。
- **F31** `if "haiku" in model:` substring tier — Asterism.yaml 化後退役，weak-tier 改顯式寫 `(builder.threshold, dispatch.shelve_threshold) = (5, 10)`。
- **F41** Verify-time LLM patch retry — 26 verify 0 觸發，F56 一起取消。實證 Step 1 開始失敗才回頭加。
- **F55 邊寫邊存版**（commit `cdb03b5`，被 `27d46bb` 取代）— 讓 agent 邊寫 PROPOSAL.md 邊 save。實作出來但用戶指出污染主任務注意力，改成 postmortem spawn 設計。

## 待辦（按優先序）

1. **(已做) entry_kind 直接 directive，刪掉 difficulty** — Backward 在每個 `new_<slug>.lean` 標 `-- entry_kind: Builder | Backward`；framework parse 進 `goals.entry_kind`；`next_worker_kind` 第一次 honor directive，attempts ≥ BUILDER_THRESHOLD 強制升 Backward 兜底。Root entry_kind 由 cli init 直接從 Manifest `## Entry kind` 段讀取。Manifest 改為直接寫 binary directive，數字 `## Difficulty` 整個從 schema / 程式 / 測試 / 文件移除（87 個 reference 全清）。

2. **(已做) TACTIC_TRY_LIST 補 `assumption` / `tauto` / `exact?`** — `A → B → A`-shaped 廢題型 Phase 1 直接收工。`linear_combination`（需係數）/ `polyrith`（需 Sage）暫不做。
3. **(已做) Infeasibility escape channel** — `decline_reason: parent_type_infeasible` PROPOSAL.md frontmatter；Builder + Backward 都可 escape；cascade 直接 shelve goal + propagate 上層重拆，不燒 attempts。SG 實證 g363 一次 spawn 內構造反例 + escape 成功。

3a. **(已做後回退) Two-phase commit-phase** — body 8min + commit 2min 嘗試打斷 thinking-dive。實證 0% 救活：Sonnet thinking block 一旦開始無法中斷，commit phase 收到 `--resume` 後再次進 thinking、120s 內 thinking 都沒生成完就被砍。session jsonl 顯示 commit prompt 後 agent 完全沒回應。回退到 body 10min + F55 postmortem 3min 單路徑。

3c. **(已做) Thinking budget cap** — env `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1` + `MAX_THINKING_TOKENS=(timeout_sec//60)*1000` 注入每次 claude spawn。1K tokens/min 對應 wall-clock 預算（body 600s→10K, postmortem 180s→3K）。Per-turn cap，agent 觸頂後強制進 output 模式但 partial thinking 保留在 session memory，下個 tool round-trip 又能 think。對症 SG 數據：dive median 9K tokens、successful median 3.7K，10K cap 切掉大半 dive、successful 損失 < 25%。在 claude_cli.py spawn 設 env、不影響其他 provider。

3b. **(已做) `_safe_glob` 防 Windows reserved-char 檔名** — agent 偶爾寫 `won_exact?.lean`（把 Lean tactic `exact?` 當識別字），Windows path API 對 `?` `<>:"|*` 拋 OSError，使 `Path.glob` 整個 dir 掃描失敗。helper 改用 `os.scandir` + `fnmatch`，跳過 path resolve 階段；單一 fix 涵蓋所有 reserved chars。
4. **SG with new framework**（已跑驗證部分機制）— F55 postmortem alternative-direction 確認有效；entry_kind 修補後 root 直接 Backward；尚未跑出完整 root proved。
4. **F38 Gemini live smoke** — quota 恢復後跑
5. **Backward placement 沒驗證 sub-goal body** — `backward.md` 約定 `new_<sub_slug>.lean` 為 `:= by sorry`，但 agent 偶爾 inline 整段 valid proof（SG s75_sub_4 實例：agent 用 `by_contra + ring + nlinarith` 多行收掉），framework 直接吞下、placement 為 `L_<slug>.lean`。**漏洞 (a)**：placement 階段 lint 缺。
6. **Dispatcher 不檢查 file 是否已 sorry-free 就 dispatch** — 承上，即使 `L_<slug>.lean` 已是 valid proof，只要 `entry_kind: Backward` 仍 spawn Backward worker 重證一次，最終 `promote_to_alias` 把 working proof 蓋掉。**漏洞 (b)**：dispatch 前應 quick lake build placeholder file，sorry-free + axioms 在白名單就直接 mark proved 跳過。SG s75_sub_4 → s76 case 實證 redundant work（重花 ~5 min spawn 一個等價 strategy）。
7. **TREE.md 在 root proved 後不更新** — `dispatcher.py:620` 的 "all roots proved" exit 分支只跑 reconcile/prune/library_promote 就 return 0，**沒呼叫 `tree.write_for_target`**。最後 `verify_housekeeping` 把 root cascade-proved 的那輪不觸發 per-cascade tree write，TREE.md 凍結在 root=attempting 的前一刻；prune 又砍 orphan 檔，TREE 內的死分支引用全失效。SG run 2026-05-05 21:10:00 root proved 後實證。**漏洞**：exit 分支應在 reconcile 後重 render 一次 TREE.md。

8. **Context.md 的失敗紀錄 4 個 section 散亂、kind-asymmetric gating** — 目前失敗訊號散在 `## Past attempts on this goal` (`show_attempts` gate, builder only) / `## Past decompositions that failed Verify` (`show_verifies` gate, backward only) / `## Builder declines` (backward only) / `## Prior strategies that died` (both 都看)。SG g142 (s83_sub_4) 實證：Backward 重試時 inline 完全看不到自己 3 次 `lake_build_error` + `parse_proposal_fail` 的歷史，只能靠 agent 主動 Read `PAST_ATTEMPTS.md`。**長期乾淨方案**：合併 4 個 section 為單一 `## Failure history`，4 個 sub-section（direct attempts / dead strategies / builder declines / verify failures）每個 ≤ 5 行 1-line digest，去掉 kind gating，全 kind 全部看；inline 是 trigger（讓 agent 知道有歷史），完整內容 fall-through 到既有 PAST_*.md companion。**不要做**：(a) 在現有架構旁加第 5 個 kind-specific section（patches 而不是 fixes 結構） (b) schema 改 dead_attempts axis 拆 agent/framework error（過度工程，資料層夠用）。預計改動：context.py 的 4 個 `_section_*` helper 合併成一個，data fetch 共用，render budget 嚴控（per-line + per-sub-section caps）。

9. **(已做) Phase 1 `tactic_try` 改用 Mathlib `hint` + 寫回精確 winner** — 演進：N 個 tactic 各跑獨立 lake build → `by first | t1 | t2 | …` 單一 build → 現在 `by hint` 兩階段 build。新流程：(1) probe 寫 `:= by hint`、lake build、parse stdout 的 `info: ... Try these: [apply] 🎉️ <tac>`、(2) confirm 把 sorry body 重寫成 `by <winner>` 再 build 一次。代價：成功時付 2 次 build（confirm 走 warm cache、便宜）。收益：搜尋集合接 mathlib `register_hint` curated set（24+ tactic、自動跟 mathlib 同步、framework 不再維護 TACTIC_TRY_LIST）；artifact 留具名 winning tactic（`won_hint.lean` 內 body 是 `:= by <具體 tac>`、不是 opaque `first | ...` 區塊）。Coverage gap：mathlib 預設 register_hint 不含 `rfl` / `assumption` / `norm_cast` / `push_cast` / `simp` / `ring_nf` / `nlinarith`，靠這幾個才能 close 的 goal 會 fall through Phase 2。實作：`Tooling/pipeline/__init__.py:_HINT_WINNER_RE + _parse_hint_winner` + `pipeline/builder.py` Phase 1 兩階段。

10. **Lake build 耗時占比沒儀表** — 目前 dispatcher log 行只記事件名（`[dispatch] ...`、`[cascade] ...`），**沒帶 timestamp**；agent jsonl 只記 agent CLI 在 session 內的時間，框架層的 `_lake_build` / `_lake_build_batch` / verify Step 1+3 都在 agent 退出後 dispatcher Python 進程內呼叫，**完全不在 jsonl**，也沒 stdout 紀錄。導致無法回答「lake build 占 spawn wall-clock 幾%」這種基本性能問題（user 問過、我先前回 50-75% 是目測印象不是測量）。**最小 instrumentation**：(a) `pipeline/_lake.py` 的 3 個 lake invocation function 加 `time.perf_counter()` 包裝，把 elapsed 寫進回傳值或 print 一行 `[lake] <target> Ns` 摘要；(b) dispatcher log lines 加 ISO timestamp prefix（一次性 logger format 改動）。完成後可以做：每 spawn 算 spawn-wall-clock vs agent-jsonl-active vs framework-lake-elapsed 三者比例，量化 (item 9) 的 `first|...` 改進實際省了多少。前置：item 9 也應該等這個 instrumentation 做完 → 可以 before/after 比較（不然只能信估算）。

11. **(已做) Dedupe `_eligible_ancestors` 過嚴，漏抓 cross-branch 等價 sub-goal** — `dedupe.py:295` 的 candidate 候選池只含 (a) candidate parent_goal_id 的**嚴格祖先鏈**上的 goals + (b) F42 同 parent 的 orphan proved sub。實證：Opus SG run 跑到 75 個 goal 時掃 statement 字串，**有 2 對 cross-branch type-identical 重複 case**：g166 (s95_sub_1, proved at depth 8) ↔ g187 (s106_sub_1, open at depth 10, 37min 後出現)；g172 (s102_sub_1, proved at depth 8) ↔ g200 (s113_sub_3, open at depth 9, 27min 後)。兩對都共一個祖先（g156 / g159）但不在彼此祖先鏈上，所以 ancestor 過濾跳過，dedup 漏。**改進**：candidate 池放寬到「同 problem 內任何 status='proved' 的 goal」（不限祖先鏈、不限同 parent）。安全性：proved goal 已是 leaf proof 沒下游依賴，alias-to-proved 永遠不形成 import cycle；只有 alias-to-open/attempting 才需 anti-cycle 檢查（沿用現行設計）。效能：candidates pool 從 ~10 升到 ~50-100，但 `_batch_isdefeq` 早就是 batched 模式，cost 線性。SG run 預估省 5-15min（每對 dedup hit 省 1-2 個 spawn × Opus 2-5min/spawn）。**不要做**：把 candidate 池無上限放寬到「any goal regardless of status」— 會引入 cycle risk，且 attempting 的 type 可能尚未穩定。

12. **Manifest 沒鼓勵預先建立 bridge lemma → 代數重複度高** — 對照 `parcadei/sylvester-gallai-lean4` 同題目實作（Mathlib `Collinear ℝ` + `Wbtw` + `Metric.infDist` 主邏輯，~1000 LOC，~30 lemma），他把所有 cross-product polynomial 工作集中在 `AreaProof.lean` ~12 個 bridge lemma（`cross2D_sq_add_inner_sq` Lagrange、`infDist_eq_cross_div_dist`、各種 cross-product 恆等式）— 寫一次、上層證明全程在 affine/metric 抽象 API 走，**重複度極低**。Asterism SG 同題目跑出 100+ sub-goal、3× LOC，主因不是 framework 性能而是**每個 sub-goal 各自重展開 cross-product**。**問題本質**：Asterism `Manifest.md` 的 `## Lemma hints` 只列 Mathlib primitives（`Finset.exists_min_image` 等），沒鼓勵 agent 在拆解早期就**預先建立 problem-specific bridge lemma 庫**。Backward worker 拆解時是 type-by-type 即興、彼此獨立，沒有「先建工具、再用工具」的階段感。**這不是 generalization 問題（推廣到更廣定理）也不是 Mathlib API 問題（換 `Collinear` 定義）**，而是 abstraction 問題：把代數工作集中在一個 bridge layer，上層邏輯不再重複 polynomial expansion。**待設計**：解法等之後再討論。可能方向：(a) Manifest 新增 `## Bridge lemmas` section、cli init 自動 placement → 自動成為 sub-goal pool 的 dedup canonical； (b) 強化 Backward prompt，引導早期 spawn 寫 type-only `Lemmas.lean`；(c) 接 item 11 dedup 擴大讓 bridge lemma 自動跨 strategy 重用。

**註記**：v3 archive (`D:\Hadamard\docs\asterism_archive\architecture_pipelines.md` §8) 的 **Generalizer pipeline** 在概念上就是 bridge lemma 的對應物 — 「讀 proved Goal G，寫候選 G\*（更廣命題使 G 是特例）」 — Lagrange identity 等 bridge 確實是 G\*。Strategist 看到「多個 sibling Goal 結構相似」就 inject Generalizer 是天然 fit。短期手動方案 (a)/(c) 可先做，長期目標是把 v3 Generalizer + Strategist coordinator 補回。Forward (corollary) 跟此問題不直接相關（先前誤判為部分解）。
5. **第三方 deep problem** — cantor 是當前最深，再要更深場景才知道 dedupe / cascade 邊界
6. **Strategist** — 拆 Backward 為 Plan + Decompose；只有 SG 在 entry_kind directive 後仍卡住才真的需要

## 重要參考

- `docs/data-flow.md` — agent 與框架資料流（F55 + F56 概念入口）
- `docs/architecture.md` — DB schema、cascade rules、pipeline 細節
- `docs/OPERATOR.md` — CLI subcommands、env vars、recurring traps

## 用戶 preferences

操作者全域 memory 在 `C:\Users\ander\.claude\projects\D--Hadamard\memory\`，本檔不重複。
