// The emoji a reaction can be (1y): a built-in list the reaction picker (messages.js) offers and searches. They are
// drawn by the system's own emoji font; nothing is loaded from anywhere. Each entry is the emoji and the words it is
// found by (English, then Traditional Chinese), never shown. The first COMMON are the picker's first row.
"use strict";
(function () {
  var A = window.Asterism;
  if (!A) return;
  var LIST = [
    ["👍", "thumbs up yes agree like ok 讚 好 同意"], ["❤️", "heart love 愛心 喜歡"], ["😂", "joy laugh tears 笑 哭笑"],
    ["🎉", "tada party celebrate congratulations 慶祝 恭喜"], ["👀", "eyes look see watching 看 眼睛"],
    ["✅", "check done yes complete 完成 勾"], ["🙏", "pray thanks please 感謝 拜託"], ["🔥", "fire hot lit 火 厲害"],
    ["👎", "thumbs down no disagree 不 反對"], ["😄", "smile happy grin 開心 笑"], ["😊", "blush smile 微笑"],
    ["🙂", "slight smile 微笑"], ["😉", "wink 眨眼"], ["😍", "heart eyes love 喜歡"], ["🤩", "star struck wow 驚艷"],
    ["😎", "cool sunglasses 酷"], ["🤔", "thinking hmm 思考 想"], ["🧐", "monocle inspect 檢查 仔細"],
    ["😮", "open mouth wow surprised 驚訝"], ["😲", "astonished shocked 震驚"], ["🤯", "mind blown exploding 腦爆"],
    ["😅", "sweat smile phew 尷尬 汗"], ["😬", "grimace awkward 尷尬"], ["😢", "cry sad tear 難過 哭"],
    ["😭", "sob crying 大哭"], ["😡", "angry rage 生氣"], ["😤", "triumph huff 哼"], ["😴", "sleep tired zzz 睡"],
    ["🥱", "yawn tired bored 打哈欠 累"], ["🤗", "hug hugging 抱抱"], ["🤝", "handshake deal agree 握手 合作"],
    ["👏", "clap applause bravo 拍手 鼓掌"], ["🙌", "raised hands hooray 萬歲 讚"], ["💪", "muscle strong flex 加油 強"],
    ["👌", "ok perfect fine 好 沒問題"], ["✌️", "victory peace 勝利"], ["🤞", "crossed fingers luck hope 祈禱 好運"],
    ["👋", "wave hello bye hi 揮手 嗨 再見"], ["☝️", "point up one 指上"], ["👉", "point right 指右"],
    ["👈", "point left 指左"], ["👇", "point down 指下"], ["🫡", "salute 敬禮 收到"], ["🤷", "shrug dunno 不知道 聳肩"],
    ["🤦", "facepalm 扶額 無言"], ["🙈", "see no evil oops 不敢看"], ["🙃", "upside down silly 反諷"],
    ["😏", "smirk 得意"], ["😐", "neutral meh 無表情"], ["😶", "speechless no mouth 無言"], ["🥳", "party celebrate 派對"],
    ["🥲", "smile tear touched 感動"], ["🥺", "pleading puppy eyes 拜託"], ["😇", "innocent halo 天使"],
    ["🤓", "nerd geek 書呆子"], ["😱", "scream fear 驚恐"], ["😳", "flushed embarrassed 臉紅"], ["🤐", "zipper secret 保密"],
    ["🤫", "shush quiet 噓"], ["🫠", "melting 融化"], ["💯", "hundred perfect score 滿分 一百"],
    ["⭐", "star favourite favorite 星星"], ["🌟", "glowing star shine 閃亮"], ["✨", "sparkles new shiny 閃亮 新"],
    ["💡", "idea bulb light 想法 點子"], ["🧠", "brain smart think 腦 聰明"], ["❓", "question 問題 問號"],
    ["❗", "exclamation important 注意 驚嘆號"], ["⚠️", "warning caution 警告 注意"], ["❌", "cross no wrong 錯 叉"],
    ["⭕", "circle correct 對 圈"], ["✔️", "check mark tick 勾"], ["➕", "plus add 加"], ["➖", "minus subtract 減"],
    ["🆗", "ok button 好"], ["🆕", "new 新"], ["🔜", "soon 快了"], ["⏳", "hourglass waiting 等 沙漏"],
    ["⌛", "hourglass done time 時間"], ["⏰", "alarm clock deadline 鬧鐘 截止"], ["📌", "pin pushpin 釘選"],
    ["📎", "paperclip attach 迴紋針 附件"], ["📝", "memo note write 筆記 寫"], ["📖", "book read 書 閱讀"],
    ["📚", "books library 書"], ["📊", "chart bar statistics 圖表 統計"], ["📈", "chart up increase 上升"],
    ["📉", "chart down decrease 下降"], ["🔍", "search magnifier look 搜尋 找"], ["🔗", "link chain 連結"],
    ["🔒", "lock locked private 鎖"], ["🔑", "key 鑰匙"], ["🛠️", "tools fix build 工具 修"], ["🔧", "wrench fix 扳手 修"],
    ["⚙️", "gear settings 設定 齒輪"], ["🧪", "test tube experiment 實驗 測試"], ["🔬", "microscope research 研究"],
    ["🧮", "abacus compute calculate 計算"], ["📐", "triangle ruler geometry 幾何"], ["📏", "ruler measure 尺"],
    ["∞", "infinity 無限"], ["🎯", "target goal bullseye 目標 命中"], ["🏁", "finish flag done 完成 終點"],
    ["🚀", "rocket launch ship 發射 上線"], ["🐛", "bug 蟲 錯誤"], ["🚧", "construction wip 施工 進行中"],
    ["🧩", "puzzle piece 拼圖"], ["🎲", "dice random 骰子 隨機"], ["🏆", "trophy win 獎盃 冠軍"],
    ["🥇", "gold medal first 第一 金牌"], ["💎", "gem diamond 鑽石"], ["💰", "money bag 錢"], ["☕", "coffee break 咖啡"],
    ["🍵", "tea 茶"], ["🍕", "pizza 披薩"], ["🍰", "cake 蛋糕"], ["🍺", "beer cheers 啤酒 乾杯"],
    ["🌈", "rainbow 彩虹"], ["☀️", "sun sunny 太陽"], ["🌙", "moon night 月亮 晚上"], ["⚡", "lightning fast zap 閃電 快"],
    ["❄️", "snow cold 雪 冷"], ["🌱", "seedling grow start 發芽 開始"], ["🌳", "tree 樹"], ["🐢", "turtle slow 烏龜 慢"],
    ["🐱", "cat 貓"], ["🐶", "dog 狗"], ["🦉", "owl night 貓頭鷹"], ["🤖", "robot bot agent 機器人"],
    ["👻", "ghost 鬼"], ["💀", "skull dead 骷髏 掛了"], ["💩", "poop 便便"], ["💥", "boom collision 爆炸"],
    ["💬", "speech comment talk 對話 留言"], ["💭", "thought bubble 想"], ["📣", "megaphone announce 公告"],
    ["🔔", "bell notify 通知 鈴"], ["🔕", "no bell mute 靜音"], ["🎵", "music note 音樂"], ["🎨", "art palette 藝術"],
    ["🧡", "orange heart 心"], ["💛", "yellow heart 心"], ["💚", "green heart 心"], ["💙", "blue heart 心"],
    ["💜", "purple heart 心"], ["🖤", "black heart 心"], ["🤍", "white heart 心"], ["💔", "broken heart 心碎"],
    ["↩️", "back return 返回"], ["⬆️", "up arrow 上"], ["⬇️", "down arrow 下"], ["➡️", "right arrow 右"],
    ["⬅️", "left arrow 左"], ["🔁", "repeat again 重複"], ["🔄", "refresh update 更新"], ["🛑", "stop 停"]
  ];
  A.emoji = {
    COMMON: 8,
    all: LIST.map(function (x) { return {emoji: x[0], words: x[1].toLowerCase()}; }),
    // The emoji whose words (or which itself) hold every word of `q`, in the list's order; the whole list for none.
    find: function (q) {
      var words = String(q || "").toLowerCase().split(/\s+/).filter(Boolean);
      if (!words.length) return A.emoji.all;
      return A.emoji.all.filter(function (x) {
        return words.every(function (w) { return x.emoji === w || x.words.indexOf(w) >= 0; });
      });
    }
  };
})();
