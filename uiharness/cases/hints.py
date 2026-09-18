# -*- coding: utf-8 -*-
"""ヒントの消費規則（GAME-SPEC 5-4）。

消費するのは**未到達の段階を初めて開いたときだけ**。見返し・閉じて開き直し・
解き直しは無料。残数 0 では未到達へ進めない。
"""

NAME = "ヒントの消費規則"


def run(ui):
    ui.open({"ci": 0, "cleared": 120, "hintStock": 3})
    ui.ev("start('course')")
    ui.check("はじめは閉じている", ui.ev("hintLv"), 0)
    ui.check("残数のバッジ", ui.text("hintstock"), "3")

    # ── 未到達の段階は 1 つにつき 1 消費 ────────────────────
    ui.click("hint")
    ui.check("1 段階目が開く", ui.ev("hintLv"), 1)
    ui.check("段階の表示", ui.ev("$('hintbox').querySelector('.hlv').textContent"), "1 / 3")
    ui.check("1 段階目は「使う記号」",
             ui.ev("$('hintbox').textContent.indexOf('使う記号')>=0"), True)
    ui.check("1 消費して残 2", ui.ev("G.hintStock"), 2)
    ui.check("バッジも追従", ui.text("hintstock"), "2")
    ui.click("hint")
    ui.check("2 段階目", ui.ev("hintLv"), 2)
    ui.check("2 段階目は「形」",
             ui.ev("$('hintbox').textContent.indexOf('形：')>=0"), True)
    ui.check("残 1", ui.ev("G.hintStock"), 1)
    ui.click("hint")
    ui.check("3 段階目", ui.ev("hintLv"), 3)
    ui.check("3 段階目は「解答例」",
             ui.ev("$('hintbox').textContent.indexOf('解答例')>=0"), True)
    ui.check("残 0", ui.ev("G.hintStock"), 0)
    ui.click("hint")
    ui.check("3 を表示中に押しても何も起きない", ui.ev("hintLv"), 3)
    ui.check("残数も減らない", ui.ev("G.hintStock"), 0)

    # ── 見返しは無料 ──────────────────────────────────────
    ui.ev("$('hint-prev').click()")
    ui.check("‹ で 2 へ戻る", ui.ev("hintLv"), 2)
    ui.ev("$('hint-next').click()")
    ui.check("› で 3 へ進む", ui.ev("hintLv"), 3)
    ui.check("見返しは消費しない", ui.ev("G.hintStock"), 0)
    ui.ev("$('hint-close').click()")
    ui.check("× で閉じる", ui.ev("hintLv"), 0)
    ui.check("到達段階は下がらない", ui.ev("hintReached()"), 3)
    ui.click("hint")
    ui.check("閉じてから押すと到達済みの 3 が無料で開く", ui.ev("hintLv"), 3)
    ui.check("残数は 0 のまま", ui.ev("G.hintStock"), 0)

    # ── 残数 0 では未到達へ進めない ───────────────────────
    ui.ev("$('hint-close').click(); go('home'); start('free')")
    ui.check("別の問題では到達段階が 0", ui.ev("hintReached()"), 0)
    ui.click("hint")
    ui.check("残数 0 なので開かない", ui.ev("hintLv"), 0)
    ui.check("残りが無いことを伝える", ui.text("sub"), "ヒントの残りがありません")

    # ── 到達済みの問題は解き直しても無料 ───────────────────
    ui.ev("G.hintStock=5; go('home'); start('course')")
    ui.check("到達 3 の問題に戻った", ui.ev("hintReached()"), 3)
    ui.click("hint")
    ui.check("いきなり 3 が開く", ui.ev("hintLv"), 3)
    ui.check("残数は減らない", ui.ev("G.hintStock"), 5)
    ui.check("減点の段階（SC.hint の表）", ui.ev("SC.hint"), [1, 0.75, 0.5, 0.3])
    ui.check("ヒントを開いてもスクロールしない", ui.scrolls(), False)
    ui.check_no_errors("ヒントを一巡しても JS エラー 0")
