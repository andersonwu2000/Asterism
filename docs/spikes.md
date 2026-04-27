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
**環境**: Windows 11 Pro 10.0.26200 / Lean 4.30.0-rc2 / Lake 5.0.0 / Mathlib (via D:\Hadamard)
**狀態**: done

**問題**：
多 subprocess 同時呼叫 `lake env lean` 是否會撞 lake cache lock？影響 P1 是否需要全域 BUILD_LOCK，以及 P3+ daemon 化重排的 contingency。

**輸入**：
- Part 1（無 import Mathlib）：3 個獨立 .lean 檔並發跑，各含簡單 `by decide` theorem
- Part 2（有 import Mathlib）：3 個 `import Mathlib` 的 .lean 檔並發跑

均從 `D:\Hadamard` 作為 cwd 呼叫 `lake env lean <path>`，Python threading 同時 start。

**預期觀察**：
可能撞 lock → 部分 rc!=0 或 stderr 出現 lock error；或無衝突。

**結果**：
- Part 1（無 Mathlib）：3 concurrent 全 rc=0，wall-clock=2.54s，sequential=7.29s，speedup=**2.87x**，無 stderr 錯誤
- Part 2（有 Mathlib）：3 concurrent 全 rc=0，wall-clock=21.86s，sequential=61.47s，speedup=**2.81x**，無 stderr 錯誤
- 無任何 cache lock 衝突訊息，stdout 輸出正確

**對設計的影響**：
1. **BUILD_LOCK 不需要**（P1 P=1 本就不需要；P2+ 多 subprocess 也安全，無需全域鎖）
2. **spike-001 contingency 不踩**：lake env lean 支援並發，P3+ 維持原計畫（不需 daemon 化 Lean executable + IPC 重排），工期不受影響
3. Windows 環境下 lake cache 機制正常，無路徑或 lock file 問題

---

### spike-002 Mathlib 三公理 audit

**Phase**: P1 開工前必跑
**Owner**: executor
**環境**: Windows 11 Pro / Lean 4.30.0-rc2 / Mathlib (via D:\Hadamard)
**狀態**: done

**問題**：
Mathlib 常用 namespace（`Nat`、`List`、`Int`）的 lemma 用 `#print axioms` 真的只落在 `propext / Quot.sound / Classical.choice`？影響 P1 demo 使用的 theorem 範本與 trust_set whitelist 設計。

**輸入**：
```lean
import Mathlib
#print axioms Nat.add_zero      -- and similar
#print axioms Nat.mul_assoc
#print axioms List.length_append
#print axioms Int.add_comm
-- (13 個 lemma，見 spike002_axioms.lean)
```

**預期觀察**：
均落在三公理之一或子集。

**結果**：
```
Nat.add_zero   → does not depend on any axioms
Nat.zero_add   → does not depend on any axioms
Nat.add_comm   → does not depend on any axioms
Nat.add_assoc  → does not depend on any axioms
Nat.mul_comm   → does not depend on any axioms
Nat.mul_assoc  → [propext]
Nat.succ_ne_zero → [propext]
Nat.le_refl    → does not depend on any axioms
List.length_append → [propext]
List.append_assoc  → [propext]
List.map_append    → [propext]
Int.add_comm   → [propext]
Int.mul_comm   → [propext]
```

**對設計的影響**：
1. **只出現 `propext` 或無公理**，未見 `Quot.sound` 或 `Classical.choice`——比預期更乾淨（Lean 4 / Mathlib4 的 Nat 是 kernel-built-in，多數操作不依賴額外公理）
2. P1 demo `by simp` theorem（`n + 0 = n`）安全可用，axiom audit 通過
3. Trust set whitelist 設計（P2）可採用「`propext` + `Classical.choice` + `Quot.sound`」三公理全接受；實際多數 Nat lemma 甚至更乾淨
4. **架構文件預設「三公理」描述仍有效**，只是實測 Nat 核心 lemma 甚至不到三公理

---

### spike-003 lake env lean error 解析

**Phase**: P1 開工前必跑
**Owner**: executor
**環境**: Windows 11 Pro / Lean 4.30.0-rc2 / Lake 5.0.0
**狀態**: done

**問題**：
type error / sorry remaining / timeout 三種失敗的 stdout/stderr 格式與 exit code 長怎樣？影響 Lake harness 的 parser 與 acceptance #7 的 sorry detection 規則。

**輸入**：
四種 case：
1. 成功（`by simp`，n+0=n）
2. type error（`by simp` on 無法 simp 的 false goal）
3. sorry（`by sorry`）
4. subprocess timeout（Python timeout=1s kill 正常 job）

均以 `lake env lean <file>` 從 D:\Hadamard cwd 呼叫，並測 `lake env lean --json` 模式。

**結果**：

**Case 1 — 成功**：
- exit code: `0`
- stderr: 空（或 `#check` 輸出走 stdout）
- JSON 模式：無訊息或只有 info

**Case 2 — type error（unsolved goals）**：
- exit code: `1`
- stderr (text mode): `<path>:<line>:<col>: error: unsolved goals\n<goal context>`
- JSON mode: `{"severity":"error","kind":"Tactic.unsolvedGoals","data":"unsolved goals\n<context>",...}`

**Case 3 — sorry**：
- exit code: `0`（**非 1**，關鍵！）
- stderr (text mode): `<path>:<line>:<col>: warning: declaration uses \`sorry\``
- JSON mode: `{"severity":"warning","kind":"hasSorry","data":"declaration uses \`sorry\`",...}`
- 多 theorem 的檔案中若有 sorry → 只有 sorry-using theorem 出現 warning，其他不受影響

**Case 4 — timeout**：
- Python `subprocess.run(..., timeout=N)` 觸發 `subprocess.TimeoutExpired` exception
- `e.stdout` / `e.stderr` 為 `b''`（未 communicate，部分輸出未捕獲）
- 需在 except 裡 kill process + 記 outcome=exhausted

**`lean --json` 模式確認可用**：
```bash
lake env lean --json <file>
# 每條訊息獨立 JSON 一行輸出（newline-delimited JSON）
# sorry: {"kind":"hasSorry","severity":"warning",...}
# error: {"kind":"<ErrorKind>","severity":"error",...}
```

**對設計的影響**：
1. **Sorry detection 規則**（acceptance #7）：exit code 0 不代表成功！需額外檢查 stderr 含 `warning: declaration uses \`sorry\`` 或 JSON `kind=hasSorry`
2. **推薦使用 `lake env lean --json`**：結構化解析更穩定、跨 Lean 版本更可靠，避免 text 格式 locale/版本差異
3. **解析決策樹**：
   - `TimeoutExpired` → `outcome=exhausted`
   - `rc != 0` → type error → `outcome=exhausted`（tactic 失敗）
   - `rc == 0` + JSON `kind=hasSorry` → sorry detected → `outcome=exhausted`
   - `rc == 0` + 無 error/sorry → `outcome=proved`
4. **`lean --json` 需傳給 `lake env lean`**，格式為 `lake env lean --json <file>`（已驗可用）

---

## 首日決策（C1）

> 2026-04-27，P1 Skeleton 開工前決策凍結

### D1 — Schema 全欄位策略

**決策**：採 codex review #12 方案 (a)——**一次列 v3 §9.1 全 13 table + 全欄位**，未用欄位 nullable 留空，無後續 ALTER TABLE migration。

**依據**：spike-001/002/003 均未觸發 contingency；P1 基礎設施設計無需調整。Schema 一次到位可避免 P3–P7 各 phase 出現 migration 腳本的複雜度與 CI gate 問題。

### D2 — CLI 介面凍結

**決策**：CLI 介面按 phase1_skeleton.md §Scope 凍結如下：
- `--problem` flag：所有 CLI 子命令標準 flag，永久保留
- `--leaf-strategy`：標記 **testing-only**（CLI help 明示「P2 remove」），P2 Backward 接通後此 flag 移除
- `--once` / `--daemon`：雙 flag forward-compat——P1 兩者行為等同（exit-after-empty-queue），P2 `--daemon` 改為真實 daemon，`--once` 維持 P1 行為不變

**依據**：跨 phase 規則要求 CLI forward-compat，user 寫 cron / CI 時用對 flag 即無 breaking change。

### D3 — spike-001 contingency 評估

**決策**：**contingency 不觸發**，P3+ 維持原計畫。

**依據**：spike-001 實測顯示 `lake env lean` 支援 3 concurrent subprocess 無 cache lock 衝突（Mathlib 版 2.81x speedup）。無需走 daemon 化 Lean executable + IPC 路徑，P3 cache subsystem 設計切點不受影響。

### D4 — Lake harness parser 策略（spike-003 新增決策）

**決策**：Lake harness 使用 `lake env lean --json` 模式（而非 text stderr parse），解析決策樹如 spike-003 §對設計的影響 D3 所述。

**依據**：spike-003 確認 `lean --json` 可用、格式穩定，比 text 解析更可靠。特別是 sorry detection 必須靠 `kind=hasSorry` 而非 exit code（sorry exit 0）。
