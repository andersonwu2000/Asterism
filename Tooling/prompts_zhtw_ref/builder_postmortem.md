你的上一輪在你 finalize patch.lean 之前就被 wall-clock timeout 殺掉了。你的 session memory 仍然保有你讀過、試過、即將做的內容。

寫一段短備註（~150 字）到 sandbox 中的 `_progress.md`。框架會把它 inline 到下一次 attempt 的 Context.md，所以下一個 spawn 從你的草稿接續。

只捕捉：

1. 證明思路（一句 — 主要 lemma family + 你打算如何組裝目標）。
2. 任何有清楚形狀的 tactic block（幾行 Lean 即可）。
3. 具體的阻塞點（不知道的 Mathlib lemma 名稱、無法 synthesize 的 typeclass instance、tactic chain 關不掉的 case）。

跳過重述目標 — Context.md 已經有了。寫 `_progress.md` 然後 exit。本輪**不要** finalize patch.lean。
