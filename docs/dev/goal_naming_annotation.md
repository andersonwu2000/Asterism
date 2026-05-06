# Goal naming + annotation

Status: Phase 1-4 shipped + PN root proved e2e (commits cab25cc / 948f557 /
cc934ff / 5be9a33 / dee781c / 400d7a7、2026-05-06). Phase 6 single-output
整合 in progress：PROPOSAL.md 退役、agent 在 patch.lean 檔頂寫 `-- ` annotation
block、decline 改用 `-- decline: <reason>` directive（success/decline 同一個檔
出口）。Phase 5（cantor/SG e2e）跟上層設計（Strategist / Forward / Generalize、
見 `bridge_lemma_layer.md`）等 Phase 6 收完再續。

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
- 只允許 `[a-z][a-z0-9_]*`（lowercase 起頭、後接 lowercase / 數字 / 底線）
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

1. Backward 拆 G → 寫 strategy s100、檔頂帶 `-- ...` annotation 進 patch.lean、
   命名 sub-goal A/B/C。framework parse 時抽 leading comments 進 `strategies.proposal_md`
2. A/B/C 各自被證掉、各自的 .lean 檔頂被 Builder（或下一層 Backward）寫上自己的
   annotation（直接寫進 patch.lean 檔頂、framework 不再 prepend）
3. s100 的 Verify 勝出 → framework 把 `s100.proposal_md` 寫進 G 的 .lean 檔頂
4. s100 若死、s120 上場、走同樣流程、annotation 永遠跟著勝出的那條

→ 每個 goal 最終 annotation 跟證它的路徑同步、不會 stale。

### 單一檔 + decline directive（Phase 6）

PROPOSAL.md 整個退役。所有 metadata 走 patch.lean 檔頂的 `--` 註解：

- success：`-- <slug>: <summary>` + body（agent 已寫對位置、framework 直接 mv）
- decline：`-- decline: too_hard | parent_type_infeasible` + 詳述、`:= by sorry` 留著

Framework parse `_extract_leading_comments` + `_extract_decline_reason` 分流。
單一 artifact、agent 心智模型統一（"a goal file is what I edit"）、framework 少一層
prepend 邏輯、forensic 走 dead_attempts.artifacts JSON 統一。

### 註解是 success 硬條件

Builder 證完沒寫 leading comment block → 視同失敗、`agent_no_annotation`、retry。
Backward 沒寫 strategy 描述同理。不強制就會漏。

## 改動清單

### Schema

- `goals.slug`：DB CHECK 不變、應用層 lint 從 `s<sid>_sub_<N>` 前綴規則改為
  charset (`[a-z][a-z0-9_]*`) / length (≤ 60) 兩檢、collision 由 framework
  auto-suffix（`Tooling/pipeline/backward.py:_resolve_slug_collisions`）
- `strategies.proposal_md`：既有 column、Verify 勝出時 propagate 進 parent .lean
- 新 shared helper：`Tooling.pipeline._format_annotation_comment(slug, body)` →
  `-- <slug>: <summary>\n-- <line2>\n...` 字串、空 body 回 ""

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
| 1 | Schema lint 改 + Backward prompt + parse 改（含 strategy 描述 + sub-goal 命名） | cab25cc + 948f557 |
| 2 | Builder annotation 強制 + Verify propagate | cc934ff |
| 3 | playbook 機制砍、F22 兩個 prompt 一起刪 | 5be9a33 + 43c3a30 |
| 4 | Context.md 加 `## Proved goals on this problem (grep entrypoint)` section | dee781c |
| 5 | PN root proved e2e validation（depth 8、21 goals） | 400d7a7 |
| 6 | single-output 整合：PROPOSAL.md 退役、agent 在 patch.lean 檔頂寫 annotation；decline 改用 `-- decline: <reason>` directive；prompt 全面精簡 | (in-progress) |

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
- Slug 機制：`Tooling/db.py:25-75`（schema）、`Tooling/pipeline/backward.py`
  charset 檢 + `_resolve_slug_collisions` helper
- Annotation helper：`Tooling/pipeline/__init__.py:_format_annotation_comment`
- Builder annotation：`Tooling/pipeline/builder.py` Phase 1 / Phase 2 success path
- Verify propagate：`Tooling/verify.py` + `Tooling/pipeline/_skeleton.py:promote_to_alias`
  的 `annotation` kwarg
- Proved-goals grep entrypoint section：`Tooling/context.py:_section_proved_goals`
- Playbook（已退役）：commit 5be9a33 砍掉 `Tooling/playbook.py` + 兩個 prompt
