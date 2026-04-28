# Cycle 目標

P6 C44 R1 (`b3e3c10`) — CLI 擴充 cluster + scheduler.py daemon hook for per-Problem pause + `--bypass-startup-check` flag。對齊 task.md ## Cycle plan P6 line 188 + phase6_library.md ## In line 54-62 (CLI 擴) + line 218 (test-only flag) + acceptance criteria #10。

預期 deliverable：
1. `Tooling/cli.py` 7 新 subcommand (`problem list/pause/resume`、`library list/check-deps/reindex/audit`、`scheduler force-clear`) + `goal add --imports CSV` flag + `run --bypass-startup-check` flag
2. `Tooling/scheduler.py` daemon-side hook：`_paused_problems: set[str]` + `_handle_control_signal` tuple branch + `_poll_db_control_signals` per-Problem forward + `_pop_queue` filtered scan + `ReactorConfig.bypass_startup_check` + `_register_scheduler` bypass branch
3. `Tooling/tests/test_cli_c44.py` 29 tests + `Tooling/tests/test_scheduler_c44.py` 16 tests
4. CI 834 → 879 pass (+45)

範圍邊界（task.md C44 line 188 + spec ## In）：純 CLI/scheduler patch；無 DB schema 改、無 lake plugin、無 promotion 邏輯動。`library reindex` / `library audit` 對齊 task.md `(stub)` 註記。

---

## R2 驗收

### 獨立驗證 — 改動範圍 vs commit message + CI

R1 (`b3e3c10`) `git diff --stat HEAD~1`：
```
 AutoWorkspace/devlog.md             |  60 ++++
 Tooling/cli.py                      | 466 +++++++++++++++++++++++++++++-
 Tooling/scheduler.py                | 209 +++++++++++---
 Tooling/tests/test_cli_c44.py       | 547 ++++++++++++++++++++++++++++++++++++
 Tooling/tests/test_scheduler_c44.py | 321 +++++++++++++++++++++
 5 files changed, 1557 insertions(+), 46 deletions(-)
```
5 files / +1557/-46。**commit message 字面與 diff 對齊**——C36/C41 的「commit message 撒謊」變種未復發。orchestrator note candidate #2 紅線連 23 cycle 監控延續、本 cycle 通過。

CI 跑 (`pytest Tooling/tests/`) 結果：**879 passed, 30 skipped, 1 xfailed in 144.90s**——commit message 834 → 879 (+45) 字面對齊。

C44 局部 run (`pytest test_cli_c44.py test_scheduler_c44.py`) 結果：**45 passed in 1.08s**。

---

### Code Review

#### 1. 必修項目（HIGH）

##### HIGH-1（spec literal 字面違反 + acceptance #10 broken；必修）：`--bypass-startup-check` 反向實作

**字面違反 phase6_library.md line 218 + acceptance #10**：

> phase6_library.md:218
> > `--bypass-startup-check`（取代 P6 草稿的 `--allow-multi-instance`）：scheduler 啟動跳過 **CLI 早期** single-instance 攔截、讓進到 liveness check 階段；**liveness check 仍正常擋**（給 acceptance #10 用）
>
> phase6_library.md:172 (acceptance #10)
> > 用 `--bypass-startup-check` flag（test-only，跳過 CLI 早期 single-instance check、讓進到 liveness check 階段）啟第二個 scheduler instance → **liveness check 偵測 first instance heartbeat 仍新 → reject 啟動** + 印錯訊息（**驗 liveness check 真的有效，不是 CLI 早期攔截**）

**Code 反向實作**（scheduler.py:337-352）：
```python
if self.config.bypass_startup_check:
    try:
        with self.conn:
            deleted = self.conn.execute(
                "DELETE FROM schedulers"
            ).rowcount
    ...
    self._emit_event(
        "control_signal",
        {"action": "startup_bypass", "rows_cleared": deleted, ...},
    )
else:
    # live check (existing C40 path) — only runs in non-bypass branch
```

→ bypass branch **DELETE 全部 schedulers row（live OR stale）+ 直接 INSERT 新 row**，liveness check 完全 skip。Spec 字面要求 bypass 應該「skip CLI 早期 check、liveness check 仍正常擋」、code 反向「DELETE 全部、liveness 永不觸發」。

**具體 acceptance fail 路徑**：
- Acceptance #10 步驟：first instance heartbeat 新 → second instance bypass → 應 reject
- 實際走當前 code：second instance bypass → DELETE first instance row → INSERT 第二 row → 兩 instance 同時運行（first 不知道自己被踢出）
- → acceptance #10 直接 fail（測 bypass 應 reject，實際 code accept）

更嚴重的 spec 違反：**operator-facing safety regression**。spec acceptance #10 backstory 是「驗 liveness check 真的有效」——當前 code 把唯一的 backstop（DB liveness）也拆了，第二實例可在 30s tick 內以「未觸發 heartbeat」狀態 INSERT，導致兩 instance 並寫 schedulers/queue/goals row（spec architecture.md:284「多 instance 並發在同一 DB 不支援 (schedulers table liveness check 防止)」字面紅線違反）。

**test 也鎖死錯誤行為**（test_scheduler_c44.py:279-301）：
```python
def test_bypass_clears_existing_rows(self, db, tmp_path):
    fresh = datetime.now(timezone.utc).isoformat()  # 新 heartbeat
    with db:
        db.execute("INSERT INTO schedulers ...", (fresh, fresh))
    reactor = _make_reactor(db, tmp_path, bypass=True)
    reactor._register_scheduler()  # 不應 raise
    rows = db.execute("SELECT COUNT(*) FROM schedulers").fetchone()[0]
    assert rows == 1  # ← 鎖死錯誤行為：fresh row 應使第二 instance reject
```

test_bypass_clears_existing_rows 把錯誤 semantics 寫入 acceptance、若 R3 修 HIGH-1 必須 ALSO 刪此 test 改為 `test_bypass_skips_cli_check_but_liveness_rejects_fresh`。

**修 HIGH-1**（建議方案）：
1. 認當前 P6 phase 沒有「CLI 早期 single-instance 攔截」（spec 假設一個未來會加的 file-lock 級 gate）；當前 code 唯一 gate 是 `_register_scheduler` 的 liveness check
2. 簡化 bypass 為 no-op + emit `startup_bypass` audit event：spec line 218「跳過 CLI 早期 攔截」此 phase 字面不適用，但 acceptance #10 「liveness check 仍正常擋」字面必須守
3. 改 test_bypass_clears_existing_rows → `test_bypass_no_op_when_only_liveness_gate_exists`：bypass=True + fresh row → 仍 raise FatalError
4. CLI `--bypass-startup-check` flag 改 emit warning「current phase has no CLI gate to bypass; liveness check still applies — use 'scheduler force-clear' for stale row cleanup」

或替代方案：bypass branch 改寫為「DELETE WHERE last_heartbeat <= cutoff (stale only)」、保留 fresh row reject 路徑——維持 acceptance #10 字面的同時提供 stale row 自動回收。

---

##### HIGH-2（spec literal 字面違反；必修）：`library audit` stub 文字不符 + 缺 exit 1

**字面違反 phase6_library.md line 62**：

> phase6_library.md:62
> > `asterism library audit`（**P6 stub**）：未來 CLI for Mathlib upgrade audit（重跑 #print axioms 對所有 Library entry 比對 trust_set snapshot）；P6 預留 **stub exit 1 + 印「not implemented; tracked in P7+」+ TODO**；避免 P7 忘記

**Code 反向實作**（cli.py:836-844）：
```python
def cmd_library_audit(args: Any, db_path: Path | None = None) -> None:
    """C44 stub for the lake-driven audit tool.

    spec phase6_library.md ## In line 38-39 字面: 「reviewer 不要寫 lake
    plugin」 + 「`tools/check_axiom_coverage.lean` Lean exe」. Real
    audit binding requires the Lean exe + lake env (P6.C45 wiring).
    """
    print("library audit: deferred (Lean exe binding lands with C45)")
    print("  for now use `library check-deps` (Python-side approximation)")
```

→ 三點字面違反：
1. **無 `sys.exit(1)`**：spec 字面要求 exit 1。當前 code return 0 silent。**silent-success 變種**——operator Mathlib upgrade flow 跑此 cmd → 0 exit code → 誤以為 audit pass。**silent-failure 紅線連 23 cycle 監控的第 9 次變種**（前 8 次：C20/C21/C24/C25/C29/C32/C36/C40 R1）。
2. **訊息文字不符**：spec 要求印「not implemented; tracked in P7+」，code 印「deferred (Lean exe binding lands with C45)」——**(a)** 缺「not implemented」字眼、**(b)** 字面誤指 C45（spec 是 P7+；C45 task.md 是 LIBRARY_BUILD_FAULT + reindex migration、不含 audit）、**(c)** 缺「TODO」inline 標記。
3. **無 inline TODO**：spec 要求「+ TODO；避免 P7 忘記」，code 無 `# TODO(P7+):` 或 `# TODO:` marker。

**修 HIGH-2**：
```python
def cmd_library_audit(args: Any, db_path: Path | None = None) -> None:
    """C44 stub per phase6_library.md ## In line 62.

    spec line 62 字面: 「P6 預留 stub exit 1 + 印「not implemented;
    tracked in P7+」+ TODO；避免 P7 忘記」. Real implementation:
    Mathlib upgrade audit (重跑 #print axioms 對所有 Library entry
    比對 trust_set snapshot) — 等 Mathlib upgrade 流程定型再做。
    """
    # TODO(P7+): bind lake-driven Mathlib upgrade audit per phase6_library.md:62
    print("library audit: not implemented; tracked in P7+", file=sys.stderr)
    sys.exit(1)
```

並更新 test_audit_stub assert exit 1 + assert "not implemented" + assert "P7+" 三條字面。

---

##### HIGH-3（silent-failure 紅線變種；必修）：`cmd_problem_list` bare `except Exception`

**Code**（cli.py:622-629）：
```python
paused: set[str] = set()
try:
    event_rows = conn.execute(
        "SELECT payload FROM events "
        "WHERE kind = 'control_signal' "
        "ORDER BY id ASC"
    ).fetchall()
except Exception:
    event_rows = []
```

bare `except Exception` 吞所有 SQL/IO 例外、**silent fallback 為 `event_rows = []`**——若 events table query fail、無任何 emit、無任何 stderr、列表所有 Problem 顯示為 "active"。

**silent-failure 紅線變種**（第 10 次連 23 cycle 監控）：
- 真實異常情況：events table schema 缺 / DB lock / disk error
- 錯誤行為：operator 看 `problem list` 輸出全 active、不知道 events table query fail、誤判 daemon 健康
- 對齊 spec architecture_impl.md / commit.py / cache.py 的「無 silent error」hard rule（P3 C21 R3 HIGH-1 + C25 R3 step1 emit-no-action 同 pattern）

**修 HIGH-3**：narrow exception + emit fallback：
```python
try:
    event_rows = conn.execute(...).fetchall()
except sqlite3.Error as exc:
    print(
        f"warning: events table query failed ({exc}); "
        "paused state may be stale",
        file=sys.stderr,
    )
    event_rows = []
```

或更嚴格：query fail 直接 raise（CLI inspect cmd 應該 fail-loud、不掩蓋）。

---

#### 2. 應修項目（MED）

##### MED-1（docstring/code drift；應修）：`_pop_queue` docstring 描述不存在的 design

**Code**（scheduler.py:1153-1164）：
```python
def _pop_queue(self) -> dict[str, Any] | None:
    """Pop highest-priority (then oldest) task. Returns None if empty.

    P6 C44 per-Problem pause: skip rows whose target's Problem is in
    self._paused_problems (re-queue stays — task is left in DB,
    spawn loop short-circuits next tick after `problem_resume`).
    Implementation walks queue in priority order until either an
    unpaused task is found or the queue exhausts; paused-row cursor
    position is via an **in-memory `_skipped_q_ids` exclusion set** so
    the scan does not re-touch the same row repeatedly within one
    spawn-loop iteration.
    """
```

實際 implementation（scheduler.py:1180-1195）：
```python
rows = self.conn.execute(
    "SELECT id, kind, target_id, payload FROM queue "
    "ORDER BY priority DESC, id ASC LIMIT 200"
).fetchall()
for q_id, kind, target_id, payload in rows:
    if self._task_problem_in_set(kind, target_id, paused):
        continue
    ...
```

→ docstring 描述「`_skipped_q_ids` exclusion set」**不存在於 code**。實際是 LIMIT 200 + linear scan。**C40 R3 HIGH-2「docstring/code 不符」變種重發**——orchestrator note candidate #2「commit 前 git show --stat 自驗」已防住 commit message 撒謊、但 docstring drift 是次一層；建議 R3 一併修。

**修 MED-1**：
- 刪 docstring 內 `_skipped_q_ids` 段
- 改寫描述為「LIMIT 200 ceiling — paused-Problem 滿 queue 時 200 row 內找 active；超過則 None（同 fast-path empty queue）」

---

##### MED-2（spec citation drift；應修）：cmd_library_audit / cmd_library_reindex 引錯 spec line

**Drift 1**（cli.py:836-844 cmd_library_audit docstring）：
> "spec phase6_library.md ## In line 38-39 字面: 「reviewer 不要寫 lake plugin」"

實際 line 38-39 是 **check-deps**（cross-Problem axiom check）的「**P6 採 CLI 手動觸發**」段、不是 audit。Audit 規格在 **line 62**。

**Drift 2**（cli.py:826-832 cmd_library_reindex docstring）：
> "spec phase6_library.md ## In line 79 字面"

實際 line 79 是 **demo bash code**（"asterism init --problem list_lemmas"）。Reindex 規格在 **line 58**（"asterism library reindex 回掃 json 補 library_index"）+ ## 任務序列 line 249（"Library reindex migration 跑過 P4/P5 既有 json"）。

**累計變種紀錄**：spec citation drift 連 C39/C40/C41/C44 4 cycle 重發（C39 R3 LOW-1 / C40 R3 MED-1「scheduler.py:262-263 spec citation comment 兩處錯」/ C41 R3 未報但本次延伸到 C44 docstring）。**orchestrator note candidate #1「Executor R1 引 spec line / section 必 grep 驗」第 4 次驗證——需正式升級為 framework rule**。

**修 MED-2**：
- cmd_library_audit docstring 引 line 62（audit 真實位置）+ 字面「P6 預留 stub exit 1 + 印『not implemented; tracked in P7+』」
- cmd_library_reindex docstring 引 line 58 + 任務序列 line 249（reindex migration 真實位置）

---

##### MED-3（spec literal 字面 drift；應修）：per-Problem control_signal payload schema 不符 spec

**字面違反 phase6_library.md:42 + line 61**：

> phase6_library.md:61
> > `asterism problem pause <p>` / `asterism problem resume <p>`：emit `control_signal(action=pause/resume, scope=problem, target=<p>)`
>
> phase6_library.md:42
> > **user 手動** `asterism problem pause <P>`（emit `control_signal(action=pause, scope=problem, target=P)`）

Spec literal payload schema：
- `action=pause/resume`（與全域 pause 同名）
- `scope=problem`（區別 global vs problem 用 scope 欄位）
- `target=<p>`（target 欄位帶 problem name）

**Code 反向實作**（cli.py:705-707, 740-742; scheduler.py:464-475）：
```python
payload = json.dumps(
    {"action": "problem_pause", "source": "cli", "problem": name}
)
```
- `action=problem_pause/problem_resume`（不是 pause/resume + scope）
- 缺 `scope` 欄位
- `problem` 欄位（不是 `target`）

**功能 OK / 字面 drift**：spec line 61 寫 `action=pause` + `scope=problem` 是「行為=pause、作用域=Problem」字面表達；code 用 `action=problem_pause` 是把 scope 拼進 action 名稱、避免與 global pause（同 events table 內）字串混用。Functionally 等價、字面不對齊。

C24 R3 / C29 R1 / C32 R1 同類「字面 drift」歷史（commit log 字面記錄）。建議 C44 R3 修齊：要麼 (A) 照 spec 字面 schema 重寫；要麼 (B) 申請 spec patch（user 介入更新 line 61）。orchestrator 決定後 R3 對應修。

**修 MED-3 建議方案 (B)**：
- 不改 code（current schema 已被 test 驗、改 schema 影響 test_scheduler_c44.py 全 16 tests）
- 改 docstring 對 spec drift 留 ack：「P6 spec line 61 字面 `action=pause + scope=problem` 改為 code-side `action=problem_pause` 避免與 global pause 同名 conflict；spec patch 留待 P7 doc-cleanup」

---

##### MED-4（docstring/code drift；應修）：`cmd_scheduler_force_clear` docstring 寫錯 default 90s

**Code**（cli.py:858-865）：
```python
def cmd_scheduler_force_clear(...) -> None:
    """DELETE schedulers rows so a new instance can register.

    Without --force: refuses to delete rows whose last_heartbeat is within
    HEARTBEAT_TTL_SEC (default 90s, per Reactor.HEARTBEAT_TTL_SEC). The
    ...
    """
```

實際 `Reactor.HEARTBEAT_TTL_SEC = 60`（scheduler.py:310）——docstring 寫「default 90s」、code 讀 60s。

**Pre-existing C40 R3 commit message 撒謊**：commit `2ccacfd` message 字面「HIGH-1 (must-fix): HEARTBEAT_TTL_SEC bumped from 60s to 90s per phase6_library.md ## Config table」、但 `git show 2ccacfd:Tooling/scheduler.py | grep "HEARTBEAT_TTL_SEC: int"` 顯示「= 60」——該 R3 commit 字面 claim 60→90 fix 但實際 code 沒改。

**C44 不引入此 bug，但 C44 R1 cli.py:861 的「default 90s」docstring 是新文字 + 把 pre-existing C40 R3 silent regression 字面再次強化**。雖屬 pre-existing scope（C40 R3 撒謊未抓到），R3 一併修：
- (a) 改 scheduler.py:310 `HEARTBEAT_TTL_SEC: int = 90` 對齊 phase6_library.md:232 Config table 字面
- (b) 改 cli.py:861 docstring 確實寫「90s, per Reactor.HEARTBEAT_TTL_SEC」（修完 (a) 後字面對齊）

或如果 90s 不適合（比如 P6 demo 過短、要 60s），則：
- (a) 改 cli.py:861 docstring 從「90s」改為「60s」對齊 code
- (b) 該 phase doc patch 改 ## Config table line 232「90s → 60s」（user 介入）

**orchestrator note**：C40 R3「字面 claim fix 但 code 沒動」屬 silent-failure 紅線變種、若計入則第 9 cycle 變種（C20/C21/C24/C25/C29/C32/C36/C40 R3 + C44 R1）。

---

#### 3. 建議項目（LOW）

##### LOW-1：`_pop_queue` LIMIT 200 ceiling 在重壓下可能造成 starvation

**Code**（scheduler.py:1184-1187）：
```python
rows = self.conn.execute(
    "SELECT id, kind, target_id, payload FROM queue "
    "ORDER BY priority DESC, id ASC LIMIT 200"
).fetchall()
```

若 queue 有 250 row、前 200 row 全屬 paused Problem、實際 row 201+ 屬 active Problem——`_pop_queue` 返 None（即便有 active task 可跑）。下次 tick 重 scan、仍卡前 200。**理論 starvation**。

P6 acceptance #1a「5 個 Problem × 各 3 root = 15 Goal」遠 < 200 不會踩；但 P7 + 真實 multi-Problem 並發、queue 容易破 200。建議：
- (a) 改用 SQL JOIN filter（query 直接 `WHERE goals.problem NOT IN (?, ?, ...)`）—— 但 ORM 動態參數綁定複雜
- (b) 把 LIMIT 200 改為 LIMIT-less，逐批 fetch（fetchmany）
- (c) 加 metric event：scan 完 200 row 仍無 hit 時 emit `paused_queue_starvation` warning

LOW 因為 P6 demo + acceptance 範圍不踩；P7+ 重壓場景再優化。

---

##### LOW-2：`_pop_queue` paused 快照與 SQL query 之間的 short race

**Code**（scheduler.py:1165-1166）：
```python
with self._lock:
    paused = frozenset(self._paused_problems)
if not paused:
    row = self.conn.execute(...).fetchone()  # lock released
```

snapshot 後 lock 釋放、若 `problem_pause` event 在 SQL 查詢中間 dispatch、daemon 可能 pop 一個剛被 pause 的 Problem 的 task。下次 tick 才會 honor 新 pause set。

**LOW** 因為：(a) race window 短（一個 SQL fetchone）；(b) functional 正確性保留——pause set 是 monotonic within tick；(c) 下次 tick 自動 catch up；(d) 與 spec acceptance 無衝突。

不建議修——加 lock 包整個 SQL fetch 會 serialize daemon loop、得不償失。

---

##### LOW-3：`_task_problem_in_set` 對 unknown kind 返 False（pop 路徑）

**Code**（scheduler.py:1226-1227）：
```python
else:
    return False  # unknown kind — don't pause unknowns
```

unknown kind 默認 `is_paused = False` → `_pop_queue` 仍 pop。註釋說「visible via `_dispatch_event` diagnostic path if mis-routed」、但這是 paused-Problem 應該被 skip 的場景下、unknown kind 反而被 pop。

實務上 P6 只有 Backward + Builder 兩 kind、unknown 不會出現；P7 加 Forward / Refuter / Generalizer 時要 extend。**LOW** 因為當前 enum 完整 + P7 必須 extend 不會漏。建議：加 inline TODO marker for P7（grep `_task_problem_in_set` 列當前 enum + flag P7 待加）。

---

#### 4. 範圍邊界 / island module 檢查

| Item | Production caller | OK? |
|---|---|---|
| `_paused_problems` set | `_pop_queue` (read) + `_handle_control_signal` (write) + `_poll_db_control_signals` → `_event_queue` → daemon loop | ✓ |
| `bypass_startup_check` | `cmd_run` → `ReactorConfig` → `_register_scheduler` | ✓ |
| `--imports` flag | `cmd_goal_add` (.lean template 寫入) | ✓ |
| `library audit/reindex` stubs | CLI dispatcher (`main()` 內 args.library_command 分支) | ✓ |
| `scheduler force-clear` | CLI dispatcher | ✓ |
| `_task_problem_in_set` helper | `_pop_queue` only caller | ✓ |

無 island module。所有新函式都有 production caller。

---

#### 5. CLI 字面對照 task.md C44 line 188

| task.md 列舉 | 實作 | 對照 |
|---|---|---|
| `problem list` | `cmd_problem_list` + parser | ✓ |
| `problem pause` | `cmd_problem_pause` + parser | ✓ |
| `problem resume` | `cmd_problem_resume` + parser | ✓ |
| `library list` | `cmd_library_list` + parser | ✓ |
| `library check-deps` | `cmd_library_check_deps` + parser | ✓ |
| `library reindex` | `cmd_library_reindex` (stub per task.md `(stub)`) | ✓ stub 標示 ok（C45 owns 真實 migration） |
| `library audit (stub)` | `cmd_library_audit` (stub) | ✗ stub 內容字面 violation（HIGH-2） |
| `scheduler force-clear` | `cmd_scheduler_force_clear` + `--force` | ✓ |
| `goal add --imports CSV` | `--imports` flag + cmd_goal_add 改寫 template | ✓ |
| `--bypass-startup-check` flag | `--bypass-startup-check` + ReactorConfig + _register_scheduler bypass branch | ✗ semantics 字面 violation（HIGH-1） |

**結論**：CLI surface 100% 符合 task.md 列舉，但 2 項（audit stub + bypass）**內部 semantics 字面違反 spec**。

---

### Acceptance gate

acceptance #10「`--bypass-startup-check` flag → liveness check 偵測 first instance heartbeat 仍新 → reject 啟動」**當前 code 不通過**——HIGH-1 要修才能通過。

acceptance criteria #1, #2, #3, #4a, #4b, #5, #6, #7, #8, #9, #11 不在 C44 範圍（C45/C46/C47 owns）。

acceptance criteria 字面 P6 「sanity gate」是 #0a Demo A+B（C46 owns），C44 R1 不需通過 sanity gate。

---

### Runtime 行為指令結果

```bash
$ pytest Tooling/tests/
============ 879 passed, 30 skipped, 1 xfailed in 144.90s (0:02:24) ============

$ pytest Tooling/tests/test_cli_c44.py Tooling/tests/test_scheduler_c44.py
============================= 45 passed in 1.08s ==============================

$ git status   # commit b3e3c10 之後 working tree 含 C45 inline 進行中改動 — 不在 C44 R1 audit 範圍
modified:   Tooling/cli.py            # cmd_library_reindex 從 stub 升 real impl (C45 work)
modified:   Tooling/library/promotion.py
```

CI 迴歸 gate ✓。45 個新 tests 全 pass。

---

## R2 累計變種統計（silent-failure 紅線連 23 cycle 監控）

C44 R1 抓到變種：
- HIGH-1 acceptance 字面違反（spec 行為與 code 行為相反）— **新類型**
- HIGH-2 silent-success（library audit 無 exit 1）— **silent-failure 紅線第 9 次變種**
- HIGH-3 bare except Exception（cmd_problem_list event query）— **silent-failure 紅線第 10 次變種**
- MED-1 docstring/code drift（_pop_queue _skipped_q_ids 不存在）— C40 R3 HIGH-2 同型
- MED-2 spec citation drift（line 38/79 寫錯）— C39/C40/C41 連 4 cycle 重發
- MED-3 schema drift（per-Problem payload schema）— 字面 drift，建議 spec patch
- MED-4 pre-existing HEARTBEAT_TTL_SEC docstring/code drift（C40 R3 silent regression）— **C40 R3 commit message 撒謊未抓到、本次延伸到 C44 cli.py:861**

**HIGH 3 + MED 4 + LOW 3 = 10 個 fixable 條目**。HIGH-1 + HIGH-2 必修才能通過 P6 acceptance；HIGH-3 為 silent-failure 紅線必修。MED 4 條全建議修齊。

C44 R1 是 **單 cycle silent-failure 紅線變種數第二高峰**（C41 R2 是 3 HIGH + 4 MED 全紅線、本次 3 HIGH 內 2 條紅線變種 + 4 MED 含 2 條紅線變種 = 4 個紅線變種）。orchestrator note candidate #3「hybrid Opus R1 對大型 cycle 變種率高」第二次驗證——本次 R1 ~870 net 行 + 3 HIGH 變種——再次證實 fresh Opus R3 的價值（但 C41 R3 hybrid inline 也成功修齊 7 條，hybrid 不是 categorical 不可行、是 cycle 規模門檻問題）。

---

## 指令

無

R3 必修 HIGH-1 + HIGH-2 + HIGH-3、應修 MED-1 ~ MED-4、建議 LOW-1 ~ LOW-3。
HIGH-1 含 test_scheduler_c44.py::TestBypassStartupCheck::test_bypass_clears_existing_rows 改寫（鎖死錯誤行為）。
HIGH-2 含 test_cli_c44.py::TestLibraryStubs::test_audit_stub 改 assert exit 1 + assert "not implemented" + "P7+"。
MED-4 涉 pre-existing C40 R3 silent regression（HEARTBEAT_TTL_SEC code 60 vs spec 90）— R3 應一併處理或標 follow-up。

orchestrator note candidate 升級建議：
- #1「Executor R1 引 spec line / section 必 grep 驗」：第 4 cycle 重發、應正式升級 framework rule
- 新 candidate「test 鎖死 R1 錯誤行為」（test_bypass_clears_existing_rows pattern）：當 R1 寫 test 時必須先用 spec 字面驗 expected behavior、不可從 code 倒推 test
