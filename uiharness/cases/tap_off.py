# -*- coding: utf-8 -*-
"""タップ配置を切ったら、選んでいた記号を放す（8.2。GAME-SPEC 4-1）。

8.1 までは、タップ配置でトレイの記号を選んだまま、設定でタップ配置をオフにして盤に戻ると、
記号が選ばれた見た目（下線）と、置き場所の枠が残っていた（実機で報告）。オフにした後はドラッグの操作なので、
残った選択は外せない（同じ記号を押してもドラッグが始まるだけ）。

ここでは、本物のマウスで記号を選び、設定のスイッチで切ってから盤に戻って、選択（held）・選ばれた見た目・
置き場所の枠が残っていないことを見る。あわせて、選択が残りうるほかの道（全部消す・ホームへ戻って入り直す・
問題を移る）と、変えていない動き（切り替えずに設定から戻れば選択は残る・オンにするときは何も放さない）も見る。
"""
import time

NAME = "タップ配置を切ると選択を放す"

PLUS = '.chip[data-op="+"]'
STATE = ("[held,document.querySelectorAll('#tray .chip.sel').length,"
         "document.querySelectorAll('#expr .zone.live').length,tapMode]")
TOKS = "T().map(x=>x.t==='num'?String(x.v):x.t==='op'?x.v:x.t==='fac'?'!':x.t==='lp'?'(':')').join(' ')"


def mouse(ui, typ, x, y):
    ui.c.ws.call("Input.dispatchMouseEvent",
                 {"type": typ, "x": x, "y": y, "button": "left",
                  "buttons": 1 if typ != "mouseReleased" else 0, "clickCount": 1})


def center(ui, sel):
    return ui.ev("(()=>{const b=document.querySelector(%r).getBoundingClientRect();"
                 "return [b.left+b.width/2,b.top+b.height/2]})()" % sel)


def tap(ui, sel, wait=0.45):
    x, y = center(ui, sel)
    mouse(ui, "mousePressed", x, y)
    mouse(ui, "mouseReleased", x, y)
    time.sleep(wait)


def set_tap(ui, back=True):
    """問題画面から設定を開き、「タップで配置する」を押して、盤に戻る"""
    ui.click("menu")
    ui.click("t-tap")
    if back:
        ui.click("navback")
        time.sleep(0.45)


def run(ui):
    ui.open({"ci": 0, "cleared": 0, "hintStock": 50})
    ui.click("m-course")
    time.sleep(0.3)
    scale0 = ui.ev("curExprScale")
    n_live = ui.ev("livePositions('+').size")

    # ── オンにして、記号を選ぶ ──
    set_tap(ui)
    ui.check("オンにしただけでは、何も選ばれていない", ui.ev(STATE), [None, 0, 0, True])
    tap(ui, PLUS)
    ui.check("記号を押すと選ばれる（下線の印・置ける場所の枠）", ui.ev(STATE), ["+", 1, n_live, True])

    # ── 変えていない動き: 切り替えずに設定から戻れば、選択は残る ──
    ui.click("menu")
    ui.click("navback")
    time.sleep(0.45)
    ui.check("設定を開いて、切り替えずに戻る: 選択と枠はそのまま", ui.ev(STATE), ["+", 1, n_live, True])

    # ── 報告の手順: 選んだまま、タップ配置を切る ──
    set_tap(ui)
    ui.check("選んだままタップ配置を切る: 選択が外れ、選ばれた見た目も、置き場所の枠も残らない",
             ui.ev(STATE), [None, 0, 0, False])
    ui.check("式の大きさは、何も選んでいないときに戻る（枠のぶんの縮小が残らない）",
             [abs(ui.ev("curExprScale") - scale0) < 1e-6, ui.ev(TOKS)], [True, ui.ev("cur.id.split('').join(' ')")])
    ui.check("保存の設定もオフ", ui.ev("G.tap"), False)
    # 切った後は、今までどおりドラッグで置ける
    x, y = center(ui, PLUS)
    mouse(ui, "mousePressed", x, y)
    mouse(ui, "mouseMoved", x, y - 6)
    time.sleep(0.45)
    tx, ty = center(ui, ".zone.live[data-p='1']")
    for k in range(1, 6):
        mouse(ui, "mouseMoved", x + (tx - x) * k / 5, (y - 6) + (ty - (y - 6)) * k / 5)
        time.sleep(0.03)
    mouse(ui, "mouseReleased", tx, ty)
    time.sleep(0.5)
    ui.check("切った後は、ドラッグで置ける（選択は無いまま）", [ui.ev(TOKS).split(" ")[1], ui.ev("held")], ["+", None])

    # ── オンにするときは、何も変えない（置いた記号も、選択が無いことも）──
    before = ui.ev(TOKS)
    set_tap(ui)
    ui.check("オンにする: 盤はそのまま・何も選ばれていない", [ui.ev(TOKS), ui.ev(STATE)], [before, [None, 0, 0, True]])

    # ── 選んで、切って、すぐ入れ直しても、選択は戻らない ──
    tap(ui, PLUS)
    ui.click("menu")
    ui.click("t-tap")
    ui.click("t-tap")
    ui.click("navback")
    time.sleep(0.45)
    ui.check("選んだまま、切ってすぐ入れ直す: タップ配置のまま・選択は外れている", ui.ev(STATE), [None, 0, 0, True])

    # ── 選択が残りうる、ほかの道（どれも元から放している）──
    tap(ui, PLUS)
    ui.click("clear")
    time.sleep(0.3)
    ui.check("選んだまま「全部消す」: 選択と枠は残らない", ui.ev(STATE), [None, 0, 0, True])
    tap(ui, PLUS)
    ui.click("back")
    ui.click("m-course")
    time.sleep(0.4)
    ui.check("選んだままホームへ戻って、入り直す: 選択と枠は残らない", ui.ev(STATE), [None, 0, 0, True])
    tap(ui, PLUS)
    ui.ev("loadPuzzle(COURSE[1])")
    time.sleep(0.3)
    ui.check("選んだまま問題を移る: 選択と枠は残らない", ui.ev(STATE), [None, 0, 0, True])
    ui.check_no_errors()
