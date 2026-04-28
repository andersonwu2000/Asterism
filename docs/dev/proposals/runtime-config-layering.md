# Runtime config layering — 全域 config 檔 + per-Problem override

## 目的

把目前散在 Python dataclass default 內的 runtime 旋鈕（`t_wall` / `lake_timeout` / `K_digest` / `D_max[*]` / `dedupe.timeout` / `N_block_after_failures` / `agent.model_defaults` / ...）抽出成兩層**檔案級**配置，讓「跑真實 Problem 時要調參數」不必改 source。

對齊 architecture v3 §8「兩層獨立配置」精神，但把目前只規範 axiom 的 META.md 擴張到 runtime 旋鈕全域。

## 動機

當前狀態（C45）：

- `cli.py cmd_run` 構造 `ReactorConfig(base_dir, bypass_startup_check)` 只傳兩個欄位
- 其餘所有 runtime 參數走 dataclass default、硬編碼在 source
- 跑 Hadamard（要 60 min t_wall + 大 lake_timeout）vs sylvester_gallai（30 min 夠）需要兩套設定 → 沒地方放
- 環境 hack：改 source、改 wrapper script、env var override 都是 ad-hoc

P7 `asterism config get/set/list` CLI 上後，**值要持久化到哪**沒答案——存 source 不對、存 DB 不便人類編、存 env 跨 session 不穩。

## 設計

### 兩層配置檔

```
Asterism/
├── asterism.yaml           # 全域 config（新增）
├── Problems/
│   └── <name>/
│       └── META.md         # YAML frontmatter（既有）+ runtime 段（新增）
```

**檔案格式統一 YAML**——META.md 已是 YAML frontmatter、`Tooling/meta.py` 解析器復用。

### 全域 `asterism.yaml`

```yaml
# Asterism 框架級 config。所有 Problem 預設套用、可被 META.md runtime 段 override。
# Schema by category（mutability 對齊 P7 `asterism config set` 行為）：

# ---- mutable: runtime 即時生效 ----
runtime:
  K_digest: 5
  K_strategist: 8
  M_strategist: 5
  ih_trap_similarity_threshold: 0.85
  strategist:
    enabled: true
    evidence_window: 20
    decisions_lookback: 10

# ---- restart-required: set 成功但 in-flight pipeline 用舊值 ----
infrastructure:
  P: 4                              # atomic pool size
  P_continuous: 1                    # continuous pool size
  tick_interval: 30.0
  T_checkpoint: 300                 # 5 min
  T_pause_max: 604800                # 7 days
  lake_timeout: 600.0
  T_wall: 1800                      # 30 min（atomic pipeline cap）

# ---- mutable per-Problem-overridable: 可被 META.md runtime 段 override ----
problem_defaults:
  N_block_after_failures: 5
  D_max:
    theorem: 12
    conjecture: 8
  dedupe:
    timeout: 30.0
    iff_lite_check_timeout: 5.0
  validator:
    max_subgoals: 8
  counterexample:
    atomic_budget_sec: 300          # 5 min
    atomic_range_default: 1000
  construction:
    atomic_budget_generations: 100
    continuous_budget_wall_clock_sec: 14400  # 4 hr
    score_plateau_generations: 20

# ---- immutable: `asterism config set` reject、編檔需重啟 + library audit ----
policy:
  Library:
    whitelist:
      - propext
      - Quot.sound
      - Classical.choice

# ---- agent runtime ----
agent:
  providers: [claude, gemini, codex]
  fallback_chain: [claude, gemini, codex]
  model_defaults:
    builder.tactic_llm: haiku
    backward.agent: sonnet
    construction_search.generate: haiku
```

### Per-Problem `META.md` runtime 段（擴張既有 frontmatter）

```yaml
---
problem_name: hadamard_4

# axioms 強制（既有，v3 §8.2）
axioms:
  - propext
  - Quot.sound
  - Classical.choice

# runtime 段（新增、全 optional）
runtime:
  T_wall: 3600                      # Hadamard construction 60 min（override global 1800）
  lake_timeout: 1800                # Mathlib-heavy
  K_digest: 10
  D_max:
    theorem: 16                     # 拆解深 problem 容忍多
  dedupe:
    timeout: 60                     # quantifier-heavy 慢
  N_block_after_failures: 8
  validator:
    max_subgoals: 12
  construction:
    continuous_budget_wall_clock_sec: 28800   # 8 hr

# models 覆寫（P7 三層 model 解析的中間層、既有 v3 §8.2 預留）
models:
  backward.agent: opus              # 整 Problem 用 opus
  construction_search.generate: sonnet
---
```

### 三層解析順序

```
最低優先  asterism.yaml (framework default)
          ↓
          Problems/<n>/META.md runtime 段 (per-Problem override)
          ↓
最高優先  Strategist decision payload (P7 已建)
```

每層只 override 自己有寫的 key、其餘 fallback 下層。

### Per-Problem-overridable keys 白名單

**適合 per-Problem override**（problem-specific 性質強）：

| Key | 為什麼適合 |
|---|---|
| `T_wall` | construction Goal 60 min、theorem 30 min 夠 |
| `lake_timeout` | Mathlib-heavy Problem 慢 |
| `K_digest` | failure_replay 抽幾條依 problem 性質 |
| `D_max[theorem]` / `D_max[conjecture]` | 拆解深度依 problem 結構 |
| `N_block_after_failures` | 難 problem 該容忍多次失敗 |
| `dedupe.timeout` / `dedupe.iff_lite_check_timeout` | quantifier-heavy 慢 |
| `validator.max_subgoals` | 複雜 problem 拆得多 |
| `counterexample.atomic_budget_sec` / `atomic_range_default` | 大 domain 要更久 |
| `construction.atomic_budget_generations` / `continuous_budget_wall_clock_sec` / `score_plateau_generations` | per-construction 預算差很大 |
| `ih_trap_similarity_threshold` | per-problem sub-Goal 結構特性 |
| `agent.model_defaults.*` | RH-dependent problem 全用 opus、toy problem 用 haiku |

**全域 only**（reactor 容量 / 政策性 / 跨 Problem 共享，META.md 寫了 reject）：

| Key | 為什麼不可 per-Problem |
|---|---|
| `P` (atomic pool size) | reactor-global 容量、per-Problem 改了不知誰贏 |
| `P_continuous` | 同上 |
| `tick_interval` | reactor 主迴圈 timing |
| `T_checkpoint` / `T_pause_max` | continuous task runtime 全域 |
| `K_strategist` / `M_strategist` | Strategist global cooldown |
| `Library.whitelist` | **政策性**——所有 Problem 共享 Library 入口、per-Problem 改破壞跨 Problem 一致性 |
| `agent.providers` / `agent.fallback_chain` | provider chain process-global |
| `schedulers heartbeat` | reactor liveness、跟 problem 無關 |

`Tooling/meta.py` parse META.md runtime 段時對 key 做 whitelist check、非 per-Problem-overridable → reject load + emit alert。

### Hard cap（防 problem owner 濫用）

framework-side 加上限：

```yaml
# asterism.yaml
problem_defaults_caps:
  T_wall_max: 14400                # 4 hr 上限、META.md 寫 5 hr → reject
  D_max_max: 32
  N_block_after_failures_max: 50
```

META.md override 超 cap → reject + 提示「需先在 asterism.yaml 提高 cap」。

### CLI 介面（P7 後擴張）

```bash
# get effective value（merge 結果、顯示來自哪層）
asterism config get T_wall
# → 1800 (asterism.yaml)

asterism config get T_wall --problem hadamard_4
# → 3600 (Problems/hadamard_4/META.md runtime)

# set
asterism config set --global K_digest 10
asterism config set --problem hadamard_4 T_wall 3600
# (寫進對應檔案、mutable 即時生效、restart-required 提示重啟)

# list 全 effective values + 來源
asterism config list --problem hadamard_4
# T_wall                  3600    (problem META.md)
# lake_timeout            1800    (problem META.md)
# K_digest                5       (asterism.yaml)
# pool_size (P)           4       (asterism.yaml; not per-Problem-overridable)
# Library.whitelist       {propext, Quot.sound, Classical.choice}  (immutable)
```

### 實作時機

**P7 完成後**作為 P7.5 或 P8 第一個 cycle slice。

前置：
- ✅ P7 `asterism config get/set/list` CLI 已上
- ✅ P7 三層 model 解析（後一層覆寫前一層）pattern 已建

新增工作量估算（4-5 cycle）：

1. **C+1**: per-Problem-overridable keys whitelist 規格 + `Tooling/meta.py` parser 擴 runtime 段 + hard cap 邏輯
2. **C+2**: `asterism.yaml` parser（`Tooling/config.py` 新建）+ ReactorConfig / BuilderConfig / BackwardConfig 等所有 dataclass 改成 「effective config」生成（merge framework + per-Problem META.md + Strategist payload）
3. **C+3**: `cli.py cmd_run` + per-pipeline spawn 邏輯改成「依 target Goal 的 Problem 重組 effective config」（這條最大、動 scheduler 多處）
4. **C+4**: CLI `asterism config get/set/list` 擴 `--problem` flag + effective value list + 來源 column
5. **C+5**: Acceptance test（hadamard_4 vs sylvester_gallai 兩 Problem 跑同 reactor、各自用對的 effective config）+ in-flight semantics test + immutable reject test
6. PR `docs/architecture/architecture.md` §8 補：
   - `§8.1` 配置表加 `mutability` + `per_problem_overridable` 兩欄
   - `§8.2` 補 META.md runtime 段 schema
   - 新建 `§8.3` 三層 model/config 解析（含 Strategist payload override）
   - 新建 `§8.4` framework-wide hard cap
7. PR `docs/architecture/architecture_impl.md` §5「Trust set 序列化 + Problem META.md」補 runtime 段 parser

## 風險

- **per-pipeline spawn 重組 effective config**：C45 已實作的 reactor.py spawn 邏輯（`_dispatch` / `_run_continuous` 等）要動，spawn Builder/Backward 時 inject 的 BuilderConfig 從「reactor 啟動時統一」改成「per-spawn 依 target Goal 的 Problem 重組」。實作量比看起來大
- **`asterism.yaml` race**：兩個 process 同時 `asterism config set` 寫 yaml → file lock 必要（locks.py P6 已建，可復用）
- **META.md auto-write 衝突**：`asterism config set --problem X T_wall 3600` 改 META.md vs user 手動編 META.md → race，同上需 lock
- **Strategist 寫 META.md 嗎**：若 Strategist 想 long-term 改某 Problem 的 K_digest、是 in-memory override 還是 persist 進 META.md？建議 **Strategist 只 in-memory override（payload 那層）、不寫 META.md**——避免 LLM 永久污染 problem 設定
- **Hard cap 反而成負擔**：對研究用途若 user 真要 8hr T_wall、cap=4hr 阻擋會煩。可配套「cap override」flag，但繞會破壞「防濫用」初衷
- **跨 Problem 不一致 debug 難**：reactor log 要明示 spawn 用的 effective config 從哪層來，否則 user 看不出為什麼兩 Problem 行為不同

## Migration（P7 → P7.5 之間）

1. 寫 `asterism.yaml` 含當前所有 dataclass default 值（idempotent migration、跑 framework 行為不變）
2. `Tooling/meta.py` 對 META.md runtime 段缺 → 不報錯（fallback to global）
3. 跑 P1-P7 既有 acceptance test，全 pass → migration 完成
4. P7+ 起新 phase 文件 cross-ref 「config 設於 asterism.yaml + 可 META.md override」、不再寫 dataclass default 數值

## 參考

- v3 §8 兩層獨立配置（框架 + per-Problem axioms）
- P7 `asterism config get/set/list` CLI（mutability category）
- P7 三層 model 解析（framework default → META.md models → Strategist payload）
- `Tooling/meta.py`（既有 META.md YAML parser、可復用）
- `Tooling/locks.py`（P6 file lock，asterism.yaml 寫入用）
