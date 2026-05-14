# Asterism — Current Status

更新於 **2026-05-15** (整補 §6 同類 bug fix)、HEAD pending commit、
802 unit tests green / 1 skipped / 1 deselected。

## TL;DR — 本 session 做了什麼

純內部 refactor / clean-up session、沒有業務功能改動：

1. **F-ID shorthand 全清**（F1-F56 / P0-P2 audit / M1-M3 / W1-W8）。整個
   code base + 現役 docs + Problem BRIEF.md 用 prose 描述、不再 dotty
   ID 名稱。decoder ring 在 `docs/archive/feature-history.md`。commit
   message 沒動。
2. **Tooling/ 重整成 7 subpackage**（Layout A）：`core/` `state/` `lsp/`
   `agent/` `quality/` `knowledge/` + 原 `pipeline/` / `llm/`。22 個檔搬
   家（含 rename：`lsp_gateway` → `lsp/gateway`、`agent.py` →
   `agent/runtime.py`、`spawn_sandbox.py` → `agent/sandbox.py` 等）。
3. **`agent.py` re-export shim 拆掉**：callers 直接 `from Tooling.agent`
   匯入（package init 還是 re-export 一份 — 那是 Python package 慣例、
   不是 shim）。
4. **`library.maybe_promote` auto-promote 機制停用** — 它把每個 proved
   problem 自動寫進 `Library/<Topic>/`、daemon 每 tick 跑、244 miniF2F
   benchmark 都被當成 library candidate（垃圾 promote）。動 root
   axiom probe 從 library 拆出來、變成 `verify.root_integrity_gate`。
   library code 留 dormant 等 user 重新設計 opt-in 機制。
5. **整 gate 永遠跑 axiom probe**：拒絕「Manifest 沒設 whitelist →
   skip」這條設計、framework 安全性不能依賴 optional field。沒設
   whitelist 時 fallback 到 `FRAMEWORK_DEFAULT_AXIOMS = (Classical.choice,
   propext, Quot.sound)` + log warning 讓 operator 看見。

## 重大不變量（refactor 改了哪些路徑）

| 舊路徑 | 新路徑 |
|---|---|
| `Tooling/cli.py` | `Tooling/core/cli.py` |
| `Tooling/dispatcher.py` | `Tooling/core/dispatcher.py` |
| `Tooling/config.py` | `Tooling/core/config.py` |
| `Tooling/db.py` | `Tooling/state/db.py` |
| `Tooling/manifest.py` | `Tooling/state/manifest.py` |
| `Tooling/tree.py` | `Tooling/state/tree.py` |
| `Tooling/brief.py` | `Tooling/state/brief.py` |
| `Tooling/recovery.py` | `Tooling/state/recovery.py` |
| `Tooling/lsp_gateway.py` | `Tooling/lsp/gateway.py` |
| `Tooling/lsp_client.py` | `Tooling/lsp/client.py` |
| `Tooling/gateway_lifecycle.py` | `Tooling/lsp/lifecycle.py` |
| `Tooling/agent.py` | `Tooling/agent/runtime.py` |
| `Tooling/context.py` | `Tooling/agent/context.py` |
| `Tooling/context_files.py` | `Tooling/agent/context_files.py` |
| `Tooling/spawn_sandbox.py` | `Tooling/agent/sandbox.py` |
| `Tooling/verify.py` | `Tooling/quality/verify.py` |
| `Tooling/library.py` | `Tooling/quality/library.py`（dormant） |
| `Tooling/dedupe.py` | `Tooling/quality/dedupe.py` |
| `Tooling/prune.py` | `Tooling/quality/prune.py` |
| `Tooling/diagnostics.py` | `Tooling/quality/diagnostics.py` |
| `Tooling/lemma_lookup.py` | `Tooling/knowledge/lemma_lookup.py` |
| `Tooling/loogle.py` | `Tooling/knowledge/loogle.py` |

操作面影響：
- CLI 入口從 `python -m Tooling.cli` 改成 `python -m Tooling.core.cli`
- agent 跑 Loogle 的 Bash whitelist 改成 `python -m Tooling.knowledge.loogle`
- `Tooling.agent` 仍可以 `from Tooling.agent import WorkArea` —
  package `__init__.py` re-export `runtime` 的 public symbols

## 本 session commit（時序）

| Commit | 內容 |
|---|---|
| `58a9d8e` | fix: integrity gate always runs axiom probe, framework default fallback |
| `3c53754` | refactor: split root-integrity gate from library auto-promote |
| `3125107` | （pre-session、非本 session 範圍）|
| `7bd48a5` | fix: Step 3 review follow-ups (blocker + minor 2/3/5) |
| `a530201` | chore: track lemma_cache.json gitignore path post-move |
| `df44f1b` | refactor: split Tooling/ into 7 subpackages (Layout A) |
| `3ae2b1b` | fix: tests calling agent._section_mathlib_hints_stable after shim removal |
| `4361a03` | docs: regenerate all BRIEF.md to pick up cleaned template |
| `710a3de` | docs: add 'verify-collapse' inline gloss to failure_modes.md |
| `113bb72` | docs: prose-ify feature IDs across docs/ |
| `a04d368` | docs+refactor: address Step 2a review feedback |
| `b298844` | docs+refactor: prose-ify feature IDs across Tooling/ |
| `a155455` | refactor: drop agent.py re-export shim |
| `ca50f58` | docs: snapshot feature ID history before code cleanup |
| `176c4ad` | chore: drop lean_shared_env/ gitignore entry |

## 後續整補（同 2026-05-15、session 重啟後）

PN smoke 觸發到上一輪沒料到的 mirror bug：dispatcher main loop 每 tick
對 `for problem_name in manifests` 跑 `verify.root_integrity_gate`、每個
root 一次 ~30s axiom_probe。整個 workspace 有 244 miniF2F + 1 PN +
sylvester_gallai = 246 proved root → 每 tick 開銷 ~110min、PN smoke 永遠
卡在 gate 階段、reach 不到 dispatch。同類於上一輪 `library.maybe_promote`
auto-promote 的設計缺陷：state-driven 應該用 marker，不是每 tick reflexive
scan。

修法：
- `goals` 加 `integrity_verified` column（migration + SCHEMA、idempotent）
- `verify.root_integrity_gate` happy path → `db.set_integrity_verified` 設 1
- `db.update_goal_status` 把 status 翻離 'proved' 時自動清 marker
  （rollback_cascade_chain 不必特別處理 — 它呼叫 update_goal_status）
- dispatcher query `db.unverified_proved_roots(conn)`、只對命中 problems
  跑 gate；244 已 proved root 跑一次後不再重跑
- migration backfill：pre-existing proved root `integrity_verified=1`、
  承認 prior daemon run 已透過舊 library 路徑跑過 axiom_probe、不重驗
- `dispatcher.run` startup 補 `db.init_schema` 呼叫、確保 migration
  在 daemon 啟動時 run（pre-existing latent bug — 之前的 migration 都靠
  cli init/reset 觸發、daemon 自己不會 migrate）

invariant tests：5 個（unverified_proved_roots empty/excludes_verified、
update_goal_status off-proved clears、ignores sub-goal、set helper persists、
init_schema 對 legacy DB backfill 既有 proved root）。

## 沒做完的事

1. **PN end-to-end smoke test**：上述 fix 後再啟動、驗證 dispatch path 真的
   走通。狀態見 commit message 或 monitor log。
2. **未 commit 的 working tree 變動 ~1555 個檔**：絕大多數是
   pre-session 累積（cantor_xi `proofs/` 大量 D、miniF2F problem 樹的
   各 Root.lean）+ 部分是這次 daemon run 寫了一半（reconcile 對 ~16
   個 problem rewritten Root.lean 但只到第 16 個就被殺）。**不要當成
   refactor 產物 commit、需要 operator 一個個檢查**。建議：
   - 跑一次 `cli run --once` 讓 reconcile pass 完成 244 個 problem、
     再一次 commit 「regenerate proved Root.lean to current canonical
     template」。但前提是 user 接受該 canonical 形式（之前那次 daemon
     寫過、似乎 user 還沒檢查）。
   - 或先 `git checkout` 那些 modified 檔、放著未變狀態、等 user 決定。

## 還在的 follow-up（從 internal_report 接過來）

- **#117** framework propagate Defs.lean opens 給 agent-authored files
  （miniF2F run 發現、cmd_init `6906399` fix 的延續）— **未動**
- **#106** Phase 2 Theorist Pipeline 設計 doc（imo_1993_p5 +
  amc12a_2009_p25 已 prove "minimal hint → IMO-tier proof" works）—
  **未動**
- **Library promotion 機制重設計**（本 session 新增）：user 已決定
  砍 auto-promote、之後依「人手 / Manifest 欄位 / etc. 自己想的方式」
  決定哪些 problem 進 Library。`Tooling/quality/library.py` 完整保留
  dormant、`Library/Misc/` 已清空、`architecture.md §10` 已重寫。
  重接時 hook 點是 dispatcher 的 per-proved-problem loop 或新 CLI command。

## 上 session 文件保留

miniF2F pilot 結果 + framework correctness gap fix + 9 errata —
`docs/internal_report_minif2f_pilot.md`、`docs/errata/minif2f/upstream_issue.md`、
`docs/proposal/`。沒動。

## 操作紀律提醒（給下個 session）

跟 `docs/CLAUDE.md` 一致、特別這幾條這次踩過：

- **F-ID 不再使用**：寫新 code / docs / commit message 都用 prose 描述 feature、
  decoder 在 `docs/archive/feature-history.md`、commit message 中可以
  引用 commit hash 但不要再開新 F-ID 編號
- **framework 安全性不能依賴 optional Manifest 欄位**：這次砍 library
  auto-promote 時、繼承的 `if not mfst.axioms_whitelist: skip` 是個
  footgun。任何 framework gate 要保證 invariant 永遠 hold、不依賴
  operator 是否填了某個欄位
- **Tooling subpackage 已穩定**：不要再大移檔；新模組往對應 subpackage
  放（domain 不明就先放 root 然後 grep 一下、別 ad-hoc 在 `Tooling/`
  root 新增）
- **大 refactor 走 subagent review**：本 session 每個 commit 後跑
  general-purpose subagent reviewer、catch 了 1 blocker + 多個 minor、
  非常划算
