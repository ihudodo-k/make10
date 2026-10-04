# -*- coding: utf-8 -*-
"""ヒントの消費規則（GAME-SPEC 5-4）。

消費するのは**未到達の段階を初めて開いたときだけ**。見返し・閉じて開き直し・
解き直しは無料。残数 0 では未到達へ進めない。

丸ボタン `#hint` は 6.4 から、箱が閉じていれば**閉じる直前の段階**を無料でもう一度出し、
開いていれば未到達の段階へ進む（友達からの報告: 1 つ見て閉じて押したら 2 つ目が開いた）。
閉じる直前の段階は開いている問題の中だけで覚え、問題の切り替え・再起動では
到達済みの最大の段階に戻る。3 まで到達済みで箱が開いている間は、どの段階を表示していても
丸ボタンが無効の色になる。
"""
import time

from uiharness import sols

# 画面に見えている段階（箱が閉じていれば "閉"）
LV = "($('hintbox').classList.contains('show')?$('hintbox').querySelector('.hlv').textContent:'閉')"


def seen(ui):
    return [ui.ev(LV), ui.text("hintstock")]

NAME = "ヒントの消費規則"


def stage3(ui):
    """段階 3 を開いたときに見える段階表示（6.9）。解答が 2 本以上の問題は、既定の表示アで
    「1/N」（1 本目を表示中）。1 本だけの問題は 6.8 と同じ「3 / 3」。
    N はゲームに聞かず、BLOB から独立に組んだ一覧（uiharness/sols.py）で数える"""
    pid, rc = ui.ev("[cur.id,cur.rc]")
    n = len(sols.load()["lists"][(pid, rc)])
    return "3 / 3" if n == 1 else "1/%d" % n


def run(ui):
    ui.open({"ci": 0, "cleared": 120, "hintStock": 3})
    ui.ev("start('course')")
    L3 = stage3(ui)          # 本編 1 問目で段階 3 を開いたときに見える段階表示
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
    ui.check("3 段階目は解答（1 本目は解答例の式）",
             ui.ev("$('hintbox').querySelector('.hbin').textContent"),
             ("解答例：" if L3 == "3 / 3" else "") + sols.pretty(ui.ev("cur.sol")))
    ui.check("3 段階目の段階表示（解答が 2 本以上なら 1/N。6.9）",
             ui.ev("$('hintbox').querySelector('.hlv').textContent"), L3)
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
    ui.check("閉じてから押すと閉じる直前の 3 が無料で開く", ui.ev("hintLv"), 3)
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

    # ── 6.4: 閉じているときは閉じる直前の段階をもう一度（消費しない）─────
    ui.open({"ci": 0, "cleared": 120, "hintStock": 5})
    ui.ev("start('course')")
    ui.check("まだ見ていない: 閉じている", seen(ui), ["閉", "5"])
    ui.click("hint")
    ui.check("見ていないときに押すと 1 つ目が出て 1 減る", seen(ui), ["1 / 3", "4"])
    ui.click("hint-close")
    ui.check("× で閉じる", seen(ui), ["閉", "4"])
    ui.click("hint")
    ui.check("【報告の再現】閉じて押すと 1 つ目がもう一度出て、減らない", seen(ui), ["1 / 3", "4"])
    ui.click("hint")
    ui.check("開いているときに押すと次へ進んで 1 減る", seen(ui), ["2 / 3", "3"])
    ui.click("hint-close")
    ui.click("hint")
    ui.check("閉じて押すと 2 がもう一度（減らない）", seen(ui), ["2 / 3", "3"])
    ui.click("hint-prev")
    ui.check("‹ で 1 へ戻る（減らない）", seen(ui), ["1 / 3", "3"])
    ui.click("hint-close")
    ui.click("hint")
    ui.check("‹ で戻ってから閉じると、戻った先の 1 が出る", seen(ui), ["1 / 3", "3"])
    ui.ev("window.__VIB=[];Object.defineProperty(navigator,'vibrate',"
          "{value:x=>{__VIB.push(x);return true},configurable:true})")
    ui.click("hint")
    ui.check("手前を見ていて押すと未到達の 3 へ進んで 1 減る（丸ボタンは新しいヒント）",
             seen(ui), [L3, "2"])
    ui.check("押して 3 に届いたときは振動する（押した時点では無効でない）",
             ui.ev("__VIB.splice(0)"), [ui.ev("DEV_DEFAULT.vibBtn")])
    # 最後まで見て開いている間は無効の色
    ui.check("3 まで見て開いている: 丸ボタンは無効",
             ui.ev("$('hint').getAttribute('aria-disabled')"), "true")
    ui.check("無効の色（--slate・半透明）",
             ui.ev("getComputedStyle($('hint')).opacity"), "0.5")
    ui.check("読み上げ用のラベル", ui.text("hintlabel").startswith("これ以上のヒントはありません"), True)
    ui.ev("__VIB.length=0")
    ui.click("hint")
    ui.check("無効のときに押しても何も起きない", seen(ui), [L3, "2"])
    ui.check("無効のときに押しても振動しない", ui.ev("__VIB"), [])
    # 3 まで到達済みなら、‹ で 1・2 に戻っても薄いまま。押しても段階もバッジも変わらず振動もしない
    for lv in (2, 1):
        ui.click("hint-prev")
        ui.check("‹ で %d に戻った" % lv, seen(ui), ["%d / 3" % lv, "2"])
        ui.check("%d を表示中も丸ボタンは無効（属性）" % lv,
                 ui.ev("$('hint').getAttribute('aria-disabled')"), "true")
        ui.check("%d を表示中も無効の色（半透明）" % lv,
                 ui.ev("getComputedStyle($('hint')).opacity"), "0.5")
        ui.check("%d を表示中のラベル" % lv,
                 ui.text("hintlabel").startswith("これ以上のヒントはありません"), True)
        ui.ev("__VIB.length=0")
        ui.click("hint")
        ui.check("%d を表示中に押しても段階もバッジも変わらない" % lv, seen(ui), ["%d / 3" % lv, "2"])
        ui.check("%d を表示中に押しても振動しない" % lv, ui.ev("__VIB"), [])
    ui.click("hint-next")
    ui.click("hint-next")
    ui.check("› で 3 に戻す（見返しは無料）", seen(ui), [L3, "2"])
    ui.click("hint-close")
    ui.ev("__VIB.length=0")
    ui.click("hint")
    ui.check("閉じた状態で押すと 3 がもう一度出て、振動もする",
             [seen(ui), ui.ev("__VIB.splice(0)")], [[L3, "2"], [ui.ev("DEV_DEFAULT.vibBtn")]])
    ui.click("hint-close")
    ui.check("閉じると無効が外れる",
             [ui.ev("$('hint').getAttribute('aria-disabled')"),
              ui.ev("getComputedStyle($('hint')).opacity")], ["false", "1"])
    ui.check("閉じているときのラベル",
             ui.text("hintlabel"), "ヒントは閉じています。押すと 3/3 をもう一度表示。残り 2")
    ui.check("見たヒントの記録（到達段階）は 3", ui.ev("G.hints[codeOf(cur)]"), 3)
    # 問題の切り替え: 閉じる直前は忘れ、到達済みの最大に戻る
    ui.ev("$('hint').click(); $('hint-prev').click(); $('hint-prev').click(); $('hint-close').click()")
    ui.check("1 まで戻って閉じた", seen(ui), ["閉", "2"])
    ui.ev("go('home'); start('free'); go('home'); start('course')")
    ui.click("hint")
    ui.check("問題を切り替えて戻ると到達済みの最大（3）が出る（減らない）", seen(ui), [L3, "2"])
    # 設定へ行って戻っても覚えている（問題は切り替わらない）
    ui.ev("$('hint-prev').click(); $('hint-close').click()")
    ui.click("menu")
    ui.click("navback")
    ui.click("hint")
    ui.check("設定へ行って戻っても閉じる直前（2）を覚えている", seen(ui), ["2 / 3", "2"])
    # 再起動: 保存しないので到達済みの最大に戻る
    ui.ev("$('hint-prev').click(); $('hint-close').click(); save()")
    time.sleep(0.4)
    save = ui.ev("JSON.parse(localStorage.getItem(SAVE_KEY))")
    ui.check("保存データに閉じる直前の段階のキーは増えない",
             sorted(k for k in save if "hint" in k.lower()), ["hintStock", "hints"])
    ui.open(save)
    ui.ev("start('course')")
    ui.click("hint")
    ui.check("再起動後は到達済みの最大（3）が出る（減らない）", seen(ui), [L3, "2"])

    # ── 6.4: ヒントを開いたまま正解すると閉じる ─────────────────
    ui.open({"ci": 0, "cleared": 120, "hintStock": 5})
    ui.ev("start('course')")
    ui.click("hint")
    ui.click("hint")
    ui.click("hint-prev")
    ui.check("正解の前: 1 を開いている", seen(ui), ["1 / 3", "3"])
    ui.ev("__solve()")
    time.sleep(0.15)
    ui.check("正解の直後（win() の前）はまだ開いている", ui.visible("hintbox"), True)
    time.sleep(0.9)
    ui.check("「つぎへ」が出ている（正解の表示）", ui.visible("wnext"), True)
    ui.check("ヒントの箱は閉じている", ui.visible("hintbox"), False)
    ui.check("閉じても見たヒントの記録は消えない", ui.ev("G.hints[codeOf(cur)]"), 2)
    ui.check("減点の段階も下がらない", ui.ev("hintMax"), 2)
    ui.click("hint")
    ui.check("正解のあと押すと閉じる直前の 1 が出る（減らない）", seen(ui), ["1 / 3", "3"])
    ui.check("「つぎへ」は出たまま", ui.visible("wnext"), True)
    ui.check_no_errors("ヒントを一巡しても JS エラー 0")
