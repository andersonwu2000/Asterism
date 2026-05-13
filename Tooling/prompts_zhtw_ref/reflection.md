你剛剛在 `{slug}` 上完成了 `{kind}`（outcome=`{outcome}`）。

`Problems/{problem}/LESSONS.md`（cap={cap}、目前 {used}/{cap} 條 bullet）：

```
{lessons_content}
```

Reflect：本次 attempt 是否暴露了一個 CROSS-SPAWN 可學習信號 — 某個本問題中**不同**目標的未來 agent 會受益的東西？

門檻 — 只有以下三項全部滿足才寫：
  - 具體（命名一個 lemma / API / namespace / goal shape）
  - 非顯而易見（fresh agent 否則會重新發現）
  - 可推廣到本目標之外

Default 是 skip。大多數 reflection 應該是 `skip`。

限制：
  - 你只能寫到 `Problems/{problem}/LESSONS.md`。**不要**碰任何其他檔案。
  - 用 Edit 工具。檔案中含有 `<!-- LESSONS_BEGIN -->` 錨點行；新 lesson 直接插在它**之後**。

Action：
  - 無信號 → exit 不編輯。
  - 有信號 + cap 未滿 → Edit 檔案，把 `<!-- LESSONS_BEGIN -->\n` 替換為 `<!-- LESSONS_BEGIN -->\n- <一句 lesson>\n`（保留錨點之後任何既有 bullet 行）。
  - 有信號 + cap 滿 → 將你的候選與每條既有 bullet 比較。如果嚴格優於最弱者，就地 Edit 最弱那行。否則 skip。

回覆其中一個：
  - `skip`
  - `wrote: <lesson>`
  - `replaced N: <lesson>`（N = 你替換的 1-indexed bullet index）

時間預算：{timeout_min} min。Edit 後立刻 exit（或 `skip` 時立即 exit）。
