# CLAUDE.md — Asterism operator 紀律

operator session 起手 auto-load（cwd 在 repo root + Read 任一 `docs/` 檔時生效）。
worker spawn 看不到本檔（F44 把 cwd 鎖在 `Problems/<p>/`、不會走進 `docs/`）。

設計細節在 `docs/architecture.md` / `data-flow.md` / `OPERATOR.md` / `STATUS.md`。
本檔只放方法論。

---

## 起手

1. `git log --oneline -15` — 真實近期狀態
2. `docs/STATUS.md` — handoff（注意它會 drift）
3. 相關設計 doc

---

## 操作規則

### 1. 不驗證的假設不能傳下去

「STATUS.md 說 SG 還沒 proved」「我以為這個 section 是最後 4 個」「我以為 prune 在
exit 才跑」— 只要下游 doc / 程式 / commit 依賴這句話，**先驗證**。
grep / `git log` / 讀對應代碼 / 跑 test，上限 5 分鐘。

Asterism 特有：design doc 的 claim 若指 commit / feature flag / file path / function /
DB column，動筆前必驗。docs 與代碼的 drift 是常態，不是例外。

### 2. 動手前先寫完成條件

DB schema migration / 跑 daemon / `prune` / 改 cascade rule / 動 docs 的入口層級（root vs
docs/）之前，把「做完必須為真」明確寫下。

例：「這次把 CLAUDE.md 放對位置 = (a) operator cwd=root 時 effectively auto-load，
(b) worker cwd=Problems/<p>/ 時不被 ancestor walk 吸到」。沒寫 → 偏離看不見、剛剛就因此
把檔放在 root。

### 3. 可逆 vs 不可逆分清楚

- **可逆**（edit / 跑 test / commit / `--once` daemon run）：直接做。
- **不可逆**（`asterism reset` / `rm asterism.db` / 手寫 sqlite update / 動 `proofs/` 既有
  檔 / `git push --force` / `prune` 不帶 `--dry-run`）：pre-flight → 驗證 → 執行。
  **永遠不趕。**

特別：daemon 跑到一半的 DB 是活的、別開另一個 process 寫它（WAL 不保護你 against
schema-level race）。

### 4. 修類別、不只修實例

解完一個 BUG，主動**尋找可能發生的方式**、決定哪些套同樣防護。沒這步 = 留同類 bug。

範例（cascade）：cascade_one 加新 outcome 分支 → 類別是「dispatcher.cascade_one /
verify.verify_housekeeping / docs §7 三點同源」→ 三處全要走一遍。

### 5. 工具輸出是敘述、不是 OK/FAIL

`lake build` 過但有 warning、`pytest` 過但 deselect 了東西、`asterism status` 顯示
`attempting` 看似正常其實 12 小時沒進展 — 每一行都在描述系統狀態。看到不預期的訊號
（dead_attempts 累積、`spawn_fast_fail` 出現、`naming_violation` 不為 0）就調查、
不當 cosmetic。

健康訊號清單見 STATUS.md「信號監控」段。

### 6. Config / schema / 文件也要 invariant test

test 不只守程式邏輯 — 也守 `Asterism.yaml` 規則、DB schema CHECK、failure_reason enum、
Manifest.md frontmatter parser、Context.md section ordering。post-mortem 結論若是
「以後要記得 X」→ **寫成 test、不是記得**。

### 7. 回報結論要附證據

送 claim 前自檢：**若被問證據，指得到哪個 commit hash / 哪個 file:line / 哪條 SQL 結果？**

- 「實測 vs 推測」分開寫、推測標「未驗證」。
- 宣稱 X 導致 Y → 要能操縱 X 看 Y 變才算測過。
- 沒辦法測的（Lean 內核行為、claude CLI 內部）直接說「沒辦法從這側測」、不要編。

### 8. 解 root cause，不 patch around symptom

設計新功能、修 bug、選依賴、決定資料流都適用。第一直覺常是「加 if 擋症狀」「補 fallback
包起來」「cache 繞過」「先用簡單版頂住」「先這樣再說」— 那是 patch、不是 fix。症狀暫時
消失或繞過、root cause 留著、下次以更難 debug 的形式回來、或變成接下來每改一處都得避開的眉角。

例（這次 session 的設計選擇、不是 bug 修復）：framework 自己維護 `TACTIC_TRY_LIST` 是
stop-gap — `by first | t1 | …` 是「簡單方案頂住」、forensic 只能記 first-block 整體、
mathlib 升級新 tactic 會落後。改接 mathlib `register_hint` curated set 是 root cause
fix：維護責任歸 mathlib、artifact 留具名 winner。

「簡單方案優先」單看會誘導 stop-gap — 跟 root cause 衝突時取後者。

---

## Asterism 特有 fact（不能由規則推出來的）

**框架狀態檔絕不手動動**（這條是規則 3 的具體 list、不重複 reasoning）：
- `asterism.db`、`.attempts/<pid>/`、`Problems/<p>/.drafts/`、`Problems/<p>/proofs/`、
  `Problems/<p>/Root.lean` — 全是框架產物。要清就走 `asterism reset` / 砍整個 DB
  從頭 init。手動動 → 下次 dispatch 行為未定義。
- 唯一人手檔：`Manifest.md` + `Defs.lean`。

**改一處 → 同步點清單**（規則 4 的具體 list）：

| 改動 | 同步點 |
|---|---|
| DB schema CHECK / 新欄位 | 寫 migration（不是改 `db.SCHEMA` 字串） |
| 新 `failure_reason` enum 值 / 新 event_type | `failure_modes.md` §2 / §3（single SoT、其他 doc 引用它） |
| `cascade_one` rule | `architecture.md` §7 + `verify.verify_housekeeping` |
| Pipeline 流程改動 | `data-flow.md` §3 Pipeline flows |
| Context.md section 變動 | `architecture.md` §12 sections 列表 |

---

## 紀律使用

- session 起手規則就 active、不用使用者提醒。
- 使用者指令與規則衝突 → 執行前先指出衝突。
- 規則 ≤ 100 行；超過搬 OPERATOR.md 或 runbook。
- 規則 cross-project 通用 → 搬 user-level CLAUDE.md。
