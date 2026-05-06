# Goal naming + annotation

Status: planned (2026-05-06). Bridge lemma layer (`bridge_lemma_layer.md`) 的前置：
Strategist / Forward / Generalize 等更上層 pipeline 都仰賴 goal 有語意的命名 +
可被 grep 找到的描述。本 doc 定形這個 substrate。

## 動機

當前 `goals.slug` 是 `s100_sub_3` 這類純結構 id，agent 從檔名看不出 goal 在做什麼。
`playbook.md` 跨 spawn 的勝利知識集中靠 F22 兩個 LLM call (extract + curate)，
多一個檔多一個同步點（前次 reset 漏清就出過事）。

Hadamard postmortem 的核心結論：agent 工作環境要 hydrate、不要把訊號量壓進 column
value。命名 + 註解是把這條落實到 Asterism。

## 設計總覽

| 項目 | 改動 |
|---|---|
| Goal 命名 | LLM 寫的 descriptive name 替代 `s<sid>_sub_<N>` |
| Goal 註解 | `.lean` 檔頂多行 comment，第一行強制 single-line summary |
| Strategy 描述 | Backward 拆解時寫進既有 `strategies.proposal_md` column |
| 註解寫入時機 | 證掉時（Builder 證完 / Strategy Verify 勝出） |
| 註解寫入者 | 葉子→Builder、非葉子→當初拆它的 Backward (strategy 描述 propagate) |
| playbook | 砍掉、F22 extract + curate 兩個 prompt 一起砍 |
| 檢索 | agent 用 grep + Read 自食其力（同 mathlib 的 grep + loogle 模式） |
| Candidate list | framework 不主動 push，最多給入口指針 |

## 細節

### 命名

- Backward 拆 G 時、一輪 LLM output 同時給：strategy 描述 + 每個 sub-goal 名字
- 名字必須 problem-local unique（DB `UNIQUE(problem, slug)` 維持）
- 衝突由 framework 自動加後綴 `_2` `_3`：agent 不檢查唯一性、framework
  重寫 sub-goal 檔的 theorem 宣告 + filename + patch.lean 的引用
- 不 lint 名字品質（爛名字是 agent 不懂該 goal 的訊號、後續 shelve 機制處理）
- 第一版不解 cross-problem 命名漂移、留到 Library 階段

`naming_violation` 從 `s\d+_sub_\d+` 格式 regex 改成：
- 非空、長度 ≤ 60
- 只允許 `[a-zA-Z0-9_]`
- 不撞既有 DB row（衝突由 framework auto-suffix、不視為 violation）

### 註解

- 第一行強制 single-line summary（grep 索引）
- 後續多行散文、無上限
- 寫進 `.lean` 檔頂 comment、DB 不另存（單一 source of truth）

格式：
```lean
-- cross_sq_add_inner_sq: |u × v|² + ⟨u,v⟩² = ‖u‖²‖v‖²
-- Lagrange identity in 2D Euclidean. Used to handle cross-product
-- expansions uniformly, avoiding repeated polynomial work downstream.
namespace Problems.sylvester_gallai
theorem cross_sq_add_inner_sq ... := by ...
```

### Strategy 描述 → goal annotation 繼承

時間軸：

1. Backward 拆 G → 寫 strategy s100 + 描述進 `proposal_md` + 命名 sub-goal A/B/C
2. A/B/C 各自被證掉、各自的 .lean 檔頂被 Builder（或下一層 Backward）寫上自己的
   annotation
3. s100 的 Verify 勝出 → framework 把 `s100.proposal_md` 寫進 G 的 .lean 檔頂作 annotation
4. s100 若死、s120 上場、走同樣流程、annotation 永遠跟著勝出的那條

→ 每個 goal 最終 annotation 跟證它的路徑同步、不會 stale。

### 註解是 success 硬條件

Builder 證完沒寫 annotation → 視同失敗、走 retry。Backward 沒寫 strategy 描述同理。
理由：不強制就會漏、漏就退化回沒命名的狀態。

## 改動清單

### Schema

- `goals.slug`：CHECK 從 `s\d+_sub_\d+` 隱含格式改為 length / 字元 lint
- `strategies.proposal_md`：從 unused → Verify 勝出時 propagate 進 parent .lean
- 新 helper：`apply_goal_annotation(goal_id, text)` 寫進對應 .lean 檔頂

### 代碼

- Backward prompt：output schema 加 `name` + strategy 描述
- Backward parse：`expected_prefix` 檢查砍掉、改 charset / length 兩檢；
  collision 由 `_resolve_slug_collisions` helper 自動加後綴並重寫
  sub-goal 檔（theorem name + filename）+ patch.lean 引用
- Builder：Phase 2 的 LLM patch output schema 加 annotation 段、success 條件加
  「annotation present」
- Verify：勝出時觸發 propagate `proposal_md` → goal .lean
- 砍 `Tooling/playbook.py`、`prompts/playbook_extract.md`、`prompts/playbook_curate.md`、
  `Tooling/cli.py:cmd_reset` 的 playbook 清理段
- 砍 Context.md 的 `## Past wins on this problem (playbook)` section
- 命名 violation check：從格式 regex 改為 length / 字元 / uniqueness

### Test

- Backward output 含 strategy 描述 + sub-goal 名字 + 唯一性衝突自動 resolve
- Builder 沒寫 annotation 視同失敗
- Verify 勝出後 parent .lean 檔頂被改寫
- 多 strategy 競爭：s100 死 s120 勝出、annotation 是 s120 的

## 開發階段

| 階段 | 內容 | Commit |
|---|---|---|
| 1 | Schema lint 改 + Backward prompt + parse 改（含 strategy 描述 + sub-goal 命名） | 1 |
| 2 | Builder annotation 強制 + Verify propagate | 1 |
| 3 | playbook 機制砍、F22 兩個 prompt 一起刪 | 1 |
| 4 | Context.md 加 `## Proved goals on this problem (grep entrypoint)` section（count + path、不 push candidate list） | 1 |
| 5 | PN / cantor / SG 重跑驗證 | (no commit) |

每階段獨立 commit、可獨立 revert。

## 不做

- name 自由文本但加複雜 lint（過度工程、第一版讓模式自然浮現）
- DB 同步存 description（雙寫同步問題、單一檔內 SoT 即可）
- 跨 problem 命名 namespace 機制（留到 Library 階段）
- 自動從 statement 萃取 name（NLP 過度工程）
- 自動 cross-goal 模式歸納（playbook curate 那種）— 改靠 agent grep 自然發現

## 待決（不影響本階段開工）

- Strategist 強度 (A/B/C) — `bridge_lemma_layer.md` 6 個開放決策點
- 預備役 status 細節
- Forward / Generalize pipeline 設計
- proved goal 的 topic_tag / usage_count 等 canonical index column

這些跟命名 + 註解獨立、可後續分開推進。命名做了反而會讓上層設計更容易（agent
看到的 inventory 更有意義）。

## 跨參考

- Bridge lemma 設計：`bridge_lemma_layer.md`
- Hadamard postmortem 教訓：`D:\Hadamard\docs\asterism_postmortem.md`
  （workspace hydration vs dehydration）
- 當前 slug 機制：`Tooling/db.py:25-75`、`Tooling/pipeline/backward.py:450-462`
- playbook 機制：`Tooling/playbook.py`、`Tooling/context.py:_section_playbook`
