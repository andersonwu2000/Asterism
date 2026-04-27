# Spikes

跨 phase spike 集中文件。每 spike 結果落本檔、phase doc 引用。

## 規則

- spike 編號**集中由本檔配發**——phase doc 草稿期出現 spike-NNN 不對 collision、開工時來本檔對齊
- 結果寫進「## 結果」段、簡明總結 + 對 phase 設計參數的影響
- 失敗 spike 也寫（負面結果同樣 actionable）
- 環境敏感的 spike（OS / Lean version / Mathlib version）標明跑的環境

## 結果格式

```
### spike-NNN <短標題>

**Phase**: P{n} 開工前必跑 / P{n} 期間
**Owner**: {orchestrator / user / executor}
**環境**: {OS / Lean version / Mathlib version / claude CLI version 等}
**狀態**: pending / running / done / failed / blocked

**問題**：
{要驗什麼、影響哪個設計參數}

**輸入**：
{要餵的具體輸入}

**預期觀察**：
{預期看到的行為 / 數值範圍}

**結果**：
{實測 + 量化數字}

**對設計的影響**：
{確認 / 改 / 推翻原 phase doc 的哪條設計選項}
```

---

## Spike 索引

依 phase 分組、編號接續配發：

### P1 必跑

- **spike-001** lake env lean 並發
- **spike-002** Mathlib 三公理 audit
- **spike-003** lake env lean error 解析

### P2 必跑

- **spike-004** claude CLI `--add-dir` 行為
- **spike-005** Lean.Elab 抽 binder list
- **spike-006** lake env lean 並發實壓
- **spike-007** claude CLI prompt token 上限

### P3 必跑

- **spike-008** IH-trap similarity metric
- **spike-009** Lean.Meta.isDefEq 性能 + iff_lite false positive
- **spike-010** search_cache hit rate 估算
- **spike-011** SQLite json_patch atomicity

### P4 必跑

- **spike-012** Counterexample agent 寫 decidable predicate 成功率
- **spike-013** Refuter witness-template 自動化
- **spike-014** cancellation propagation 對 lake 子程序
- **spike-015** evaluator_hash composition

### P5 必跑

- **spike-016** lean_synth mutation operator 可行性
- **spike-017** Python scorer subprocess sandboxing
- **spike-018** Lean type-check 速度 vs candidate 數
- **spike-019** gemini / codex CLI scope-isolation 對齊
- **spike-020** per-provider 同 prompt 品質對照

### P6 必跑

- **spike-021** lake build Library 子模組速度
- **spike-022** fcntl on Windows
- **spike-023** 跨 Problem import 行為
- **spike-024** 跨 Problem theorem name 解析

### P7 必跑

- **spike-025** P7 baseline 量測
- **spike-026** Strategist agent prompt 可行性
- **spike-027** Generalizer agent 寫 G* 成功率
- **spike-028** Forward 從 negation seed 推
- **spike-029** Strategist model override 反饋值

---

## 結果

（依編號逐一 append，未跑的不出現）

---

### spike-001 lake env lean 並發

**Phase**: P1 開工前必跑
**Owner**: executor
**環境**: Windows 11 Pro 10.0.26200 / Lean 4.30.0-rc2 / Lake 5.0.0-src+3dc1a08 / Python 3.12 / Mathlib (via D:\Hadamard)
**狀態**: done

**問題**：
多 subprocess 同時呼叫 `lake env lean` 是否會撞 lake cache lock？影響 P1 是否需要全域 BUILD_LOCK、P3+ daemon 化重排的 contingency。同時驗 phase1_skeleton.md ## 風險 第 4 條：`tactic_try` 同檔反覆改寫 .lean 跑 lake，cache 是否依檔案內容失效（不會誤判 pass）。

**輸入**：
- Part 1（無 import Mathlib）：3 個獨立 .lean 檔並發跑，各含 `by decide` theorem
- Part 2（有 import Mathlib）：3 個含 `import Mathlib` 的 .lean 檔並發跑
- Part 3（cache invalidation extension）：1 個 .lean 檔同路徑寫 3 次（PASS `1+1=2 by decide` → FAIL `1+1=3 by decide` → PASS），逐次跑 `lake env lean`

均從 `D:\Hadamard` cwd 呼叫，Python threading 同時 start，`subprocess.PIPE` capture stdout/stderr。

Fixture：`Tooling/tests/fixtures/spikes/spike001_{a,b,c,mathlib_a,mathlib_b,mathlib_c}.lean` + `spike001_concurrent.py` + `spike001_mathlib_concurrent.py` + `spike001_cache_invalidation.py`（Mathlib 升版後可重跑驗漂移）。

**預期觀察**：
可能撞 lock → 部分 rc!=0 或 stderr 出現 lock error；或無衝突；cache invalidation 預期 round 2 rc=1。

**結果**：
- Part 1（無 Mathlib）：3 concurrent 全 rc=0，wall-clock=**2.54s**，sequential=**7.29s**，speedup=**2.87x** — 近線性加速
- Part 2（有 Mathlib）：3 concurrent 全 rc=0，wall-clock=**21.86s**，sequential=**61.47s**，speedup=**2.81x** — 與 sequential 相當（warm cache 跑法）
- Part 2 額外跑（cold cache 跑法，每 process 強制重載 .olean）：3 concurrent **224.14s** vs sequential **63.24s**，concurrent **慢 3.54x**——每個 lean 程序載入 Mathlib 全量 .olean（估計數 GB）並發 → 磁碟 IO 競爭 + 記憶體壓力，無資料損壞但效果上等同串行化
- Part 3（cache invalidation）：rc1=0 (2.39s) → rc2=1 (2.42s, stdout `error: Tactic \`decide\` proved that the proposition 1 + 1 = 3 is false`) → rc3=0 (2.40s)。**lake 確實依檔案內容重 elab，無 stale cache 命中**
- 兩種並發跑法均無 cache lock error，stderr 均空，stdout 輸出正確

**對設計的影響**：
1. **無 cache lock 衝突，BUILD_LOCK 不需要**（P1 P=1 本就不需要；P2+ 多 subprocess 也安全）
2. **spike-001 contingency 不踩**：lake 支援並發、無 lock 衝突、無資料損壞——不滿足「lake 完全無法並發」的 contingency 條件，P3+ 不需 daemon 化 Lean executable + IPC，工期維持
3. **P3+ Mathlib-importing 並發上限建議 P=1–2**：cold cache 並發因 IO/memory 競爭嚴重退化（3.54x 慢）；warm cache（短時間內重複呼叫同檔 / 共享 .olean）下 P=3 仍 OK。Builder `tactic_try` 同檔重跑屬 warm 場景，安全。短 `lake env lean` 呼叫（無 Mathlib import 的 staging 驗證）並發更高無顧慮
4. **Builder `tactic_try` cache invalidation 安全**（phase1_skeleton.md ## 風險 第 4 條解除）：lake 對同一路徑的 .lean 改寫會重 elab，不會誤判 pass。C5 Builder 實作可放心採「同 staging 路徑反覆改寫」策略
5. Windows 環境下 lake cache 機制正常，無路徑或 lock file 問題

---

### spike-002 Mathlib 三公理 audit

**Phase**: P1 開工前必跑
**Owner**: executor
**環境**: Windows 11 Pro / Lean 4.30.0-rc2 / Mathlib (via D:\Hadamard)
**狀態**: done

**問題**：
Mathlib 常用 namespace（`Nat`、`List`、`Int`、Classical、Finset、Real）的 lemma 用 `#print axioms` 真的只落在 `propext / Quot.sound / Classical.choice`？影響 P1 demo 使用的 theorem 範本，以及 P2+ trust_set whitelist 是否覆蓋實務 Mathlib 依賴。

**輸入**：
```lean
import Mathlib
-- 基礎 Nat / List / Int（13 lemma）
#print axioms Nat.add_zero        -- 以及 zero_add / add_comm / add_assoc /
#print axioms Nat.mul_comm        -- mul_comm / mul_assoc / succ_ne_zero / le_refl
#print axioms List.length_append  -- List.append_assoc / map_append
#print axioms Int.add_comm        -- Int.mul_comm
-- demo theorem 本身
theorem add_zero_simple (n : Nat) : n + 0 = n := by simp
#print axioms add_zero_simple
-- Classical / Finset / Real / Multiset（驗三公理路徑真的會出現）
#print axioms Classical.em
#print axioms Finset.sum_comm
#print axioms Multiset.card_add
#print axioms Real.sqrt_nonneg
```

Fixture：`Tooling/tests/fixtures/spikes/spike002_{axioms,classical,real,demo}.lean`。

**結果**：

Nat / List / Int 基礎 lemma：
```
Nat.add_zero      → does not depend on any axioms
Nat.zero_add      → does not depend on any axioms
Nat.add_comm      → does not depend on any axioms
Nat.add_assoc     → does not depend on any axioms
Nat.mul_comm      → does not depend on any axioms
Nat.mul_assoc     → [propext]
Nat.succ_ne_zero  → [propext]
Nat.le_refl       → does not depend on any axioms
List.length_append → [propext]
List.append_assoc  → [propext]
List.map_append    → [propext]
Int.add_comm       → [propext]
Int.mul_comm       → [propext]
```

Demo theorem（不同證法、同 statement）：
```
add_zero_simple (n : Nat) : n + 0 = n := by simp        → [propext]
add_zero_rfl    (n : Nat) : n + 0 = n := Nat.add_zero n → does not depend on any axioms
mul_one_ring    (n : Nat) : n * 1 = n := by ring        → [propext]
le_add_right'   (n m : Nat) : n ≤ n + m := by omega     → [propext, Quot.sound]
```

Classical / Finset / Real（高層）：
```
Classical.em       → [propext, Classical.choice, Quot.sound]
Finset.sum_comm    → [propext, Classical.choice, Quot.sound]
Multiset.card_add  → [propext, Quot.sound]
Real.sqrt_nonneg   → [propext, Classical.choice, Quot.sound]
```

**對設計的影響**：
1. **Nat 核心 lemma 比預期更乾淨**：多數無公理或只用 `propext`。`Quot.sound` 從 `omega` 開始出現（Multiset 內部用），`Classical.choice` 在 Classical / Finset / Real 層必出現
2. **P1 demo `by simp` theorem `n+0=n` axiom = `[propext]`** ⊆ 三公理集合 → P2 trust_set validation 通過。demo 範本 axiom-clean，可直接用
3. **Trust set whitelist `{propext, Quot.sound, Classical.choice}` 設計實務有效**：本 spike 確認 Classical / Finset / Real 路徑都落在這三公理子集內，未見其他公理（如 sorryAx、用戶自訂 axiom）。P2 whitelist 接受規則實作可放心
4. **架構文件「三公理」描述對齊**：Lean 4 / Mathlib4 的高層 lemma 確實只依賴這三公理或子集

---

### spike-003 lake env lean error 解析

**Phase**: P1 開工前必跑
**Owner**: executor
**環境**: Windows 11 Pro / Lean 4.30.0-rc2 / Lake 5.0.0-src+3dc1a08 / Python 3.12
**狀態**: done

**問題**：
type error / sorry remaining / timeout 三種失敗的 stdout/stderr 格式與 exit code 長怎樣？影響 Lake harness 的 parser 與 acceptance #7 的 sorry detection 規則。Windows 下 subprocess timeout 是否能正確殺 lake 子程序？

**輸入**：
- Case 1：通過（`theorem test_a : 1 + 1 = 2 := by decide`）
- Case 2：type error / unsolved goals（`theorem t (n : Nat) : n + 0 = n + 1 := by simp`、type mismatch `def bad : Nat := "hello"`、unknown tactic）
- Case 3：sorry（單 theorem + 多 theorem + term-level `:= sorry`）
- Case 4：subprocess timeout（Python `subprocess.run(timeout=1)` kill 正常 lake 呼叫）

均以 `lake env lean <file>` / `lake env lean --json <file>` 從 `D:\Hadamard` cwd 呼叫，Python `subprocess.PIPE` 個別 capture。

Fixture：`Tooling/tests/fixtures/spikes/spike003_{sorry,sorry_nolib,sorry_multiple,type_error,type_error_nolib,more,unsolved,unknown_tactic}.lean` + `spike003_runner.py` / `spike003_runner2.py`。

**結果**（**所有 lean 訊息走 stdout，stderr 永遠為空**——關鍵糾正！）：

**Case 1 — 通過**：
- exit code: `0`
- stdout: 空（或 `#check` info 輸出）

**Case 2 — type error / unsolved goals**：
- exit code: `1`
- stdout（text）：`<path>:<line>:<col>: error: <message>\n<goal context>`，例如 `D:\...\spike003_type_error.lean:3:53: error: unsolved goals\nn : ℕ\n⊢ False`
- stdout（`--json`）：`{"severity":"error","kind":"Tactic.unsolvedGoals","data":"unsolved goals\n...","fileName":"...","pos":{...},...}`
- 其他 error kind：`lean.synthInstanceFailed`、自訂 message error 等

**Case 3 — sorry**：
- exit code: **`0`**（**非 1**，關鍵！sorry 不影響 lean 本身是否 typecheck）
- stdout（text）：`<path>:<line>:<col>: warning: declaration uses \`sorry\``
- stdout（`--json`）：`{"severity":"warning","kind":"hasSorry","data":"declaration uses \`sorry\`","fileName":"...","pos":{...},...}`
- 多 sorry → 每個 sorry-using theorem 各出現一條 warning；其他 theorem 不受影響

**Case 4 — subprocess timeout**：
- Python `subprocess.run(..., timeout=N)` 觸發 `subprocess.TimeoutExpired`
- `e.stdout` / `e.stderr` 為部分資料（buffered，未 communicate）
- **Windows process-tree caveat**：`subprocess.run(timeout=...)` 只 kill 直接 child（lake.exe），不一定殺到孫程序（lean.exe）。Lake harness 必須在 except 內走 process-tree kill（`taskkill /F /T /PID <pid>` 或 `psutil.Process(pid).children(recursive=True)`），不能單 PID kill

**`lake env lean --json` 已驗可用**：
```
# sorry:
{"kind":"hasSorry","severity":"warning","data":"declaration uses `sorry`",...}
# type error:
{"kind":"Tactic.unsolvedGoals","severity":"error","data":"unsolved goals\n...",...}
# info (#check):
{"kind":"[anonymous]","severity":"information","data":"Nat.add_comm : ...",...}
```

**對設計的影響**：
1. **所有 lean 輸出走 stdout，stderr 永遠空**——parser 只讀 stdout，不要寫成 stderr
2. **Sorry detection 規則**（acceptance #7）：exit code 0 ≠ pass！必須額外偵測 stdout 含 `warning: declaration uses \`sorry\`` 或 JSON `kind=hasSorry`
3. **採用 `lake env lean --json` 模式**：結構化解析（JSON per line）比 text regex 穩定，跨 Lean 版本可靠
4. **Lake harness 解析決策樹**（pipeline 層級的最終判定，**不**是 `tactic_try` 內部 loop 的 per-tactic 判定。`tactic_try` 拿到 rc!=0 是「換下一個 tactic」、所有 tactic 試完才走「outcome=exhausted」）：
   ```
   subprocess.TimeoutExpired          → outcome=exhausted（process-tree kill）
   rc != 0                            → outcome=exhausted（type error / tactic failure）
   rc == 0 + JSON kind=hasSorry      → outcome=exhausted（sorry detected）
   rc == 0 + 無 error/sorry           → outcome=proved
   ```
5. **Windows timeout 必走 process-tree kill** 而非單 PID kill（phase1_skeleton.md ## 風險 第 2 條對齊）；C2 Lake harness 實作 timeout path 採 `psutil` 或 `taskkill /T`

---

## 首日決策（C1）

> 2026-04-27，P1 Skeleton 開工前決策凍結

### D1 — Schema 全欄位策略

**決策**：採 codex review #12 方案 (a)——**一次列 v3 §9.1 全 13 table + 全欄位**，未用欄位 nullable 留空，無後續 ALTER TABLE migration。

**依據**：codex review #12（phase1_skeleton.md ## Scope 第 1 條已凍結為 (a) 路）的核心理由是避免 P3–P7 各 phase 出現 ALTER TABLE migration 腳本的 CI gate 複雜度（每次 schema 改 → migration 寫 + 跨 phase 迴歸 + 舊 DB 升級路徑驗證）。決策本身與 spike-001/002/003 結果無因果關係（schema 結構與 lake / 公理 / error format 三議題不交集）；本 cycle 只負責確認此決策不被 spike 結果推翻——三 spike 均未發現需動 schema 的事證，決策維持。

### D2 — CLI 介面凍結

**決策**：CLI 介面按 phase1_skeleton.md §Scope 凍結如下：
- `--problem` flag：所有 CLI 子命令標準 flag，永久保留
- `--leaf-strategy`：標記 **testing-only**（CLI help 明示「P2 remove」），P2 Backward 接通後此 flag 移除
- `--once` / `--daemon`：雙 flag forward-compat——P1 兩者行為等同（exit-after-empty-queue），P2 `--daemon` 改為真實 daemon，`--once` 維持 P1 行為不變

**依據**：跨 phase 規則要求 CLI forward-compat，user 寫 cron / CI 時用對 flag 即無 breaking change。

### D3 — spike-001 contingency 評估

**決策**：**contingency 不觸發**，P3+ 維持原計畫。

**依據**：contingency 觸發條件為「lake 完全無法並發（彼此干擾、cache lock 撞死、資料損壞）」。spike-001 實測：無 cache lock 衝突、無資料損壞、無 stderr error；Mathlib cold-cache 並發雖因 IO/記憶體競爭性能退化（3.54x 慢）但**不**屬於「無法並發」——僅需 P3+ Mathlib-importing 呼叫限 P=1–2 即可。無需走 daemon 化 Lean executable + IPC 路徑，P3 cache subsystem 設計切點不受影響。Cache invalidation extension 額外確認 Builder `tactic_try` 同檔反覆改寫安全（phase1_skeleton.md ## 風險 第 4 條解除）。

### D4 — Lake harness parser 策略（spike-003 新增決策）

**決策**：Lake harness 使用 `lake env lean --json` 模式（讀 stdout，不讀 stderr），解析決策樹如 spike-003 §對設計的影響 #4 所述。Timeout path 採 process-tree kill（Windows `taskkill /F /T` 或 `psutil`）。

**依據**：spike-003 確認 (a) 所有 lean 輸出走 stdout、stderr 永遠空；(b) `lean --json` 可用、JSON per-line 穩定；(c) sorry exit code = 0、必須靠 JSON `kind=hasSorry` 偵測；(d) Windows subprocess timeout 默認只殺直接 child，必須 process-tree kill 才不留孫程序 lean.exe。
