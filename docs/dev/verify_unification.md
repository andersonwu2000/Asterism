# Verify path unification — gateway as single olean producer

把 framework runtime 對 `lake build` 的依賴從 verify path 全部拔掉、
統一走 gateway worker pool。所有 verify、olean 寫入、axiom probe 都在
warm Mathlib worker 內完成、`lake build` 只剩 library promote 那一次。

狀態：設計定稿、待實作。

---

## 1 動機 & 既有狀況

Phase 2.5 step 1（commit `4a89201`）把 Builder Phase 2 verify 從 cold
`lake build` 換成 `gateway.check_build`、預期 ~10-30s → ~3-4s。但後續發
現兩個問題：

1. **Stale olean false-positive**（commit `3ca764b` 修復）：gateway didChange
   只更新 worker 記憶體、不寫 olean。後續 `axiom_probe` 走 `lake env lean`
   讀 disk olean、可能讀到 stale 版本（mtime 判斷被 `shutil.copy2` 騙）。
   修法是 axiom_probe 之前先 `lake build` 一次，但這把 Phase 2.5 的速度
   優勢吃掉一半 ── 改成 gateway verify (~3-4s) + lake build (~10-15s) +
   lake env lean (~1-2s) ≈ ~14-21s、跟 cold lake build 直接做差不多。

2. **Cascade verify 的多檔依賴**：verify_strategy / Backward placed-batch
   裡 parent-imports-strategy 或 strategy-imports-sub-goals 的依賴鏈、
   Lean import 解析靠 disk olean、worker 記憶體跨 slot 不通。

結果：Phase 2.5 只有「失敗路徑」（壞 patch 早 abort）真的省、成功路徑
其實**比 cold lake build 還慢一點**。多檔 verify 完全沒遷。

要根除 cold lake build 需要解決：「**gateway 也能寫 olean**」。

---

## 2 為何 olean 寫入是關鍵

Lean 的 module import 在 elaborate 階段**只查 olean 檔**（不會去讀 source
重 elaborate）。worker 之間記憶體 isolated、跨 slot 看不到彼此 environment。

只要 gateway 寫 olean、所有後續操作 ── 下一層 cascade verify、axiom
probe 經由 import 拉、library promote 的 re-export ── 全部能用同一份
warm Mathlib worker 處理。`lake build` 變成「真有需要產生 olean 給外部
consumer」才呼叫的工具、不是 verify 路徑的一環。

**寫 olean 的成本是「幾乎免費」**：

| 步驟 | 成本 |
|---|---|
| didChange + elaborate | 3-5s（warm Mathlib） |
| `Lean.writeModule` 序列化 + flush | ~50-200ms |
| 下層 cascade 透過 disk olean 讀回 | mmap 即時 |

序列化只是把已 elaborate 完的 `Environment` 寫成 bytes、不重做計算。

---

## 3 為何放棄拼接、改成 per-file queue

之前考慮過「所有跨 import 檔拼接成 single slot content、單 didChange
elaborate 全部」。**只要 gateway 寫 olean、拼接就完全不需要**：

```
verify_strategy 流程 (per-file queue):
  1. didChange to slot: strategy file
  2. elaborate ok? write olean to disk
  3. didChange to slot: parent file
     parent 的 import strategy_module 解析到 disk olean → ok
  4. elaborate ok? write olean
  5. RPC printAxioms(parent.main, parent_module) → 拿 axiom set
```

對比 concat 的優勢：

| 維度 | Concat | Per-file queue |
|---|---|---|
| Diagnostic line 號 | 需 server side offset map + 回傳前 remap | 自然對應原檔、零工程 |
| `private` decl 跨檔污染 | 風險（雖然我們生成檔不用 private） | 零風險 |
| 平行 sub-goals（同層獨立檔） | ❌ 一坨大 elaborate | ✅ 多 slot 真平行 |
| 深樹 cascade | quadratic（每層重 elaborate 整個子樹） | linear（每檔一次、olean cache 給下層用） |
| 程式語意 | Server side 拼字串、邏輯散落 | 每檔獨立、跟 lake 概念對齊 |

歷史深度資料：

| Problem | depth | goals | branching |
|---|---:|---:|---:|
| proj_nonexpansive (現) | 3 | 6 | 3 |
| wilson (haiku-bak) | 2 | 10 | 9 |
| **wilson (haiku-f37-bak)** | **5** | **33** | **4** |

Monsky / Hadamard 級的目標問題會到 8-12 層、上百 goals。Concat 在
這級會 quadratic 退化（root 級每次拼幾百檔上萬行）；per-file queue
跟 lake 一樣 linear。

### 3.1 兩階段收斂：parent verify → 完全 mechanical

per-file queue 在 SG-19 上跑出 cascade 慢的問題（10 層、每層 2 個
verify_file ≈ 36s × 10 = 6 min）。觀察 cascade verify 的攔截能力：

**所有 sorry 注入點都已經在「葉子層」被攔截**：
- Builder leaf：`pipeline/builder.py` 在 commit 時 axiom_check（有 axioms_for）
- Backward leaf-bypass：`pipeline/backward.py:624-670` acceptance 時 axiom_check
- 非葉子 strategy patch compile：`pipeline/backward.py:851` submit 時 verify

唯一沒在 submit 時驗的：**非葉子 strategy patch 本身的 sorry**。submit 時
sub-goal 還是 sorry-stub、`#print axioms` 看到的 sorryAx 無法分辨「自己寫的 sorry」
跟「stub 帶來的 sorry」。

這個檢查可推到 root：所有 sub-goal alias-in 後、`axiom_probe(Root.lean)` 看到
main 用 sorryAx 即代表某 strategy 漏。**Bisect 找元凶 cost 1-2s、只在 rare
failure 時付**。

**第一階段（b8b6bc0）**：parent verify 拿掉、scratch verify 加 `axioms_for=scratch_fq`。
6 min → 3.5 min。

**第二階段（本 commit）**：cascade 完全 mechanical、root 才驗：

```
verify_strategy (mechanical-only):
  1. promote_to_alias(parent)              # 純字串模板、microsecond 級
  2. return "proved"                       # 不呼叫 verify_file

library.maybe_promote (cascade 完成後，integrity gate):
  3. axiom_probe(Root.lean, axioms_for=main_fq)
     - 唯一 Lean elaboration 點
     - lake serve worker 走完整 alias 鏈、缺 olean 的 L_*.lean on-demand elaborate
     - 抓 promote_to_alias drift（compile error → Lean 印檔名+行號）
     - 抓任何漏網 sorryAx（rogue axioms: [sorryAx]）
  4a. 若 ok → cleanup_cascade_backups + Library/<topic>/ 推進
  4b. 若 rogue 含 sorryAx：
      - bisect_sorryax_source：對每個 'succeeded' strategy 跑 #print axioms
        找第一個 scratch 含 sorryAx（deepest first）
      - rollback_cascade_chain：從元凶往 root 走、restore 每層 alias backup、
        revert DB state（元凶 'dead'/'open'、上游 'proposed'/'attempting'）
      - dispatcher re-check root_proved、繼續 main loop、下一個 tick re-Backward
```

收斂進度對照：

| 維度 | per-file queue | scratch-only (b8b6bc0) | mechanical-only (此 commit) |
|---|---|---|---|
| 每層 verify_file 次數 | 2 | 1 | 0 |
| SG-class 10-level cascade 時間 | ~6 min | ~3.5 min | ~10s + root verify ~30-60s |
| 每層 olean 寫入磁碟 | scratch + parent | scratch | 無新寫入（scratch.olean 在 submit time 已寫）|
| Per-strategy 編譯錯誤偵測 | cascade time | cascade time | submit time（backward.py:851）|
| Per-strategy sorryAx attribution | parent fq | scratch fq | failure path bisect（1-2s）|
| Cascade 失敗復原 | 本層 rollback | 本層 rollback | bisect + rollback 整鏈 |

empirical justification — cascade verify 「攔到過什麼」：

| Run | Cascade verify 次數 | 攔到 |
|---|---|---|
| F56 doc 統計（cantor + proj_nonexpansive 早期）| 26 | 0 |
| SG run #19 | 10 | 0 |
| PN refactor run | 5 | 0 |
| **合計** | **41** | **0** |

s378 sorryAx 案例（SG #19 唯一 caught sorryAx）發生在 **Backward leaf-bypass
submit time、不是 cascade**。Mechanical-only 設計把零收益的 41 次 verify 全
省掉、failure path 用 bisect 補回 attribution。

---

## 4 設計

### 4.1 三個自訂 LSP RPC（Lean 端）

寫一個 Lean 模組（mathlib loogle 同模式）、註冊三個 custom JSON-RPC
method 到 `lake serve` 的 worker：

| Method | 參數 | 回傳 |
|---|---|---|
| `$/asterism/writeOlean` | `{ uri, destPath }` | `{ ok, bytesWritten }` |
| `$/asterism/printAxioms` | `{ fqName, module }` | `{ axioms: list[str] }` |
| `$/asterism/queryEnv` | `{ fqName }`（debug 用） | `{ exists, kind }` |

實作要點：
- `writeOlean` 走 `Lean.Environment.writeOleanFile` / `Lean.Module.toOleanBytes`
  (確切 API 名以 toolchain pin 版本為準)。輸入是當前 worker
  `RequestM` 拿到的 environment、指定輸出 path 寫到 `.lake/build/lib/lean/`
  下對應位置
- `printAxioms` 走 `Lean.collectAxioms` / `Lean.Elab.Print.collectAxiomsOf`、
  拉 fqName 的 transitive axiom dependencies 回成 list
- 寫 olean 後**立即** `flush` + `fsync`、確保 disk 同步、避免下一輪 didChange
  讀到半寫狀態

### 4.2 三個 gateway HTTP endpoint

```
POST /verify
  body: { target_path: str, write_olean: bool = true }
  return: { ok: bool, diagnostics: [...], olean_written: bool }

POST /verify_batch
  body: { paths: [str], dependency_order: [str]? }
  return: { results: [{path, ok, diagnostics, olean_written}] }
  - 若 dependency_order 提供、按該順序序列化執行
  - 否則檢測獨立檔（無互相 import）、平行分派多 slot
  - 任一檔 fail、後續依賴它的檔自動 skip

POST /axioms
  body: { fq_name: str, module: str }
  return: { ok: bool, axioms: [str], error: str? }
```

`/verify` 邏輯：
1. 拿 file content from disk
2. acquire slot（LRU + sticky-by-content）
3. didChange to slot URI（**不是** target file 的 URI）
4. wait_for_diagnostics_settled
5. 若 ok 且 write_olean=true：發 `$/asterism/writeOlean` RPC、target_path
   推導出 olean dest（`.lake/build/lib/lean/<module-path>.olean`）
6. 回 diagnostics + olean_written

`/verify_batch` 邏輯：
1. 解析依賴關係（`dependency_order` 顯式提供、或 server 從 `import`
   stmt parse 得到拓撲序）
2. 同層獨立檔：`asyncio.gather` 多 slot 平行 verify
3. 跨層依賴：等前層 olean 寫完才進下一層
4. 任一檔 fail 立刻 short-circuit、回部分結果

`/axioms` 邏輯：
1. acquire slot
2. didChange 一個 placeholder 包含 `import <module>` （或重用已 load 該
   module 的 slot）
3. 發 `$/asterism/printAxioms` RPC
4. 回 axiom list

### 4.3 Python 端 client

```python
# Tooling/gateway_lifecycle.py 加：
def verify_file(target_path, *, write_olean=True, workspace=None) \
    -> tuple[bool, str, bool]: ...

def verify_batch(paths, *, dependency_order=None, workspace=None) \
    -> dict[Path, tuple[bool, str]]: ...

def axiom_probe_via_gateway(*, fq_name, module, whitelist, workspace=None) \
    -> tuple[bool, str]: ...
```

### 4.4 Migration map

| 原 callsite | 新呼叫 | 動作 |
|---|---|---|
| `builder.py:120,126` Phase 1 hint probe | `verify_file` + parse `[apply] 🎉️` from info diagnostic | 改 `_parse_hint_winner` |
| `builder.py:300` Phase 2 verify | `verify_file(write_olean=true)` | 升級現有 `check_build` 呼叫 |
| `backward.py:567` leaf-bypass | `verify_file(write_olean=true)` | 升級現有 `check_build` 呼叫 |
| `backward.py:763` placed batch | `verify_batch([strategy] + sub-goals)` | drop-in |
| `verify.py:93` verify_strategy | `verify_batch([strategy, parent], dep_order=[strategy, parent])` | drop-in |
| `_axiom.py:35` axiom_probe | `axiom_probe_via_gateway` | drop-in、subprocess code 砍 |
| `library.py:140` promote axiom check | `axiom_probe_via_gateway` | drop-in |

### 4.5 砍除清單

完整遷移後：

| 檔案/函式 | 動作 |
|---|---|
| `Tooling/pipeline/_lake.py` 的 `_lake_build`, `_lake_build_batch`, `_lake_build_modules` | DELETE（runtime 不再 lake build） |
| `Tooling/pipeline/_axiom.py` 的 subprocess + regex 路徑 | DELETE |
| `gateway_lifecycle.check_build` | RENAME / REPLACE 成 `verify_file` |
| `Tooling/lsp_gateway.py` 的 `/check_build` endpoint | RENAME 成 `/verify` |

保留 `lake build` 呼叫只剩：
- `library.promote` 完成的最終 build（per-Problem 1 次、為 Library/ 寫
  olean 給外部 consumer）── 不在 hot path
- `cli init/reset` / `cli doctor` 的 file-system 邊角操作

---

## 5 風險 & mitigation

### 5.1 Lean API 漂移

`Lean.writeModule` / `Lean.collectAxioms` 是 internal API、Lean 4.x → 4.y
可能改名。

Mitigation：
- Pin toolchain（`lean-toolchain` 已 pinned）
- 自訂 Lean 模組放 import 區塊註明 minimum Lean version
- 升 Mathlib / Lean 時跑 integration test、抓 breaking
- 寫 fallback：若 RPC fail（API gone）、log error 並退回 cold lake build

### 5.2 Gateway-produced olean ↔ lake-produced olean 等價性

擔心：gateway 寫的 olean 跟 lake 寫的 olean **可能 metadata 不完全一致**
（例如 hash、build dependency tracking）、後續 `lake build` 可能拒收要重 build。

Mitigation：
- Integration test：gateway 寫 olean → 跑 `lake build <module>` → 確認
  rc=0、且 lake **不**重 build（mtime / hash 視為 fresh）
- 對 Lean 的 olean 序列化方式做寫入：確保 magic header、version、
  module name、dependency graph、checksum 都正確
- 真出問題的話、退路是「gateway 寫 olean 後立刻 `lake build` 確認」
  ── 等於 verify 兩次但保正確性、相當於 Option B 的退化

### 5.3 並行 didChange 對同一 olean dest

兩個 slot 同時 verify 不同 file 但 olean dest 撞名（不該發生但邊界 case）。

Mitigation：
- olean dest 由 module name 推導、不重複名就不撞
- write 前 atomic rename: 先寫 `.olean.tmp` 再 rename
- 加 file lock（`fcntl.flock` Unix / `msvcrt.locking` Windows）

### 5.4 Worker 記憶體膨脹

長 cascade run 累積很多檔的 elaborated state。

Mitigation：
- 每寫完 olean 立刻 didChange 該 slot 回 `import Mathlib\n` warmup state、
  釋放 file-specific elaborate state
- Slot LRU 淘汰機制本來就會處理（commit `fbf65ac`）

---

## 6 預估工程量 & wall time benefit

### 6.1 LOC

| 項 | LOC |
|---|---:|
| Lean side custom RPC handler | +100 |
| Gateway endpoints + slot orchestration | +200 |
| Python client | +50 |
| Callsite migration（7 處） | +50 |
| 砍 `_lake.py` lake_build* + `_axiom.py` subprocess | -300 |
| Tests（unit + olean integrity + 深樹 cascade） | +150 |
| **Net** | **+250** |

### 6.2 Wall time（典型 cascade）

| 場景 | 現狀 | Option C |
|---|---|---|
| Builder Phase 2 verify (single file, success) | ~14-21s | ~3-5s |
| Builder Phase 2 verify (single file, fail) | ~3-4s（早 abort） | ~3-4s（早 abort） |
| verify_strategy (2 files) | ~25-50s | ~6-10s |
| Backward placed batch (4 files) | ~40-80s | ~10-15s（多 slot 平行） |
| axiom_probe (per call) | ~10-15s + ~1-2s | ~50-200ms |

### 6.3 深樹案例（Monsky 級、depth 10、200 goals）

| 路徑 | wall time |
|---|---|
| 現狀（cold lake at every cascade） | ~10-15 分 |
| Option A (concat) | ~30+ 分（quadratic） |
| **Option C** | **~3-5 分** |

---

## 7 實作順序

一次完成、避免半遷狀態。建議分支 `verify-unification` 離 main 約 1 週、
完成後 squash merge。

1. Lean side：寫自訂 RPC 模組、跑 manual test 確認 `writeOlean`、
   `printAxioms` 工作
2. Gateway side：加 `/verify`、`/axioms` endpoint、加 client
3. Migration：逐個 callsite 改、跑 unit test
4. `/verify_batch`：實作平行 slot 分派
5. 砍 `_lake_build_*` + `_axiom.py` subprocess code
6. Integration test：完整 cascade run（用測試 problem）、驗證
   gateway-produced olean 跟 lake-produced 行為等價
7. 跑 PN 一輪、確認 wall time benefit
8. squash merge to main

---

## 8 Open questions

- **Olean 寫入的 atomic rename 還是直接 write？** 想用 atomic rename（先
  `.tmp` 再 `os.replace`）、避免半寫狀態被 lake 看到。但 LSP RPC handler
  在 worker 內、Lean 寫 olean 的 API 是否支援 destination 指定 `.tmp` 後
  自己 rename、或需要 Python 側 wrap RPC 呼叫做 rename ── 待 Lean 端 API 確認

- **`/verify_batch` 的依賴分析**：顯式 `dependency_order` 由 caller 提供
  vs server side parse `import` stmt 自動算拓撲。前者明確、後者通用。
  傾向**先做顯式**（caller 傳）、簡單明白；之後若有需要再加 auto。

- **Builder Phase 1 hint 的 diagnostic parse**：Mathlib `hint` tactic
  的 info diagnostic 訊息格式可能跨版本變動（`Try these:` / `[apply]
  🎉️ <tac>` / 其他）。需 robust regex + 對 hint 失敗（無 winner）的明
  確處理。建議實作前先用一個 lean 檔手動驗 hint 在 worker 的 publishDiagnostics
  shape

---

## 9 為何不更激進（gateway 完全取代 lake）

`lake build` 的**最終 olean for external consumer**（library promote 路
徑）仍走 lake：
- Library/ 下 re-export 檔要被 user 自己的 lean 工程 import
- 那些 import 解析還是要 disk olean
- 我們可以全 cascade gateway verify、但**最後一次** library promote 的
  build 用 lake、確保產出的 olean 跟 mathlib 標準工具鏈完全相容

這條 1 次/Problem、~30s、不在 hot path、不必動。如果以後 gateway-produced
olean 經完整驗證真的 100% 等價 lake、再砍。
