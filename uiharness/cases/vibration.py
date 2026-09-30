# -*- coding: utf-8 -*-
"""振動（6.4。GAME-SPEC 5-6）。

headless Chrome は振動しないので、navigator.vibrate を差し替えて
呼ばれた回数と長さを __VIB に記録する。設定の「振動」がオンのときだけ、
ドラッグ（つまむ・枠の上・置く）とボタンで振動することを見る。
ドラッグは CDP のマウス操作で本物の pointer イベントとして起こす。
"""
import time

NAME = "振動（ドラッグとボタン）"

STUB = """
window.__VIB=[];
Object.defineProperty(navigator,'vibrate',
  {value:function(x){__VIB.push(x);return true},configurable:true});
"""


def vib(ui):
    return ui.ev("__VIB.splice(0)")        # 読んだら空にする


def mouse(ui, typ, x, y):
    ui.c.ws.call("Input.dispatchMouseEvent",
                 {"type": typ, "x": x, "y": y, "button": "left",
                  "buttons": 1 if typ != "mouseReleased" else 0, "clickCount": 1})


def center(ui, sel):
    return ui.ev("(()=>{const b=document.querySelector(%r).getBoundingClientRect();"
                 "return [b.left+b.width/2,b.top+b.height/2]})()" % sel)


def drag_plus(ui):
    """トレイの + をつまんで、最初に開いた枠へ置く"""
    x0, y0 = center(ui, '.chip[data-op="+"]')
    mouse(ui, "mousePressed", x0, y0)
    time.sleep(0.4)                         # 枠が開くのを待つ
    x1, y1 = center(ui, ".zone.live")
    for i in range(1, 9):
        mouse(ui, "mouseMoved", x0 + (x1 - x0) * i / 8, y0 + (y1 - y0) * i / 8)
        time.sleep(0.03)
    time.sleep(0.2)
    mouse(ui, "mouseReleased", x1, y1)
    time.sleep(0.4)


def run(ui):
    ui.open({"ci": 0, "cleared": 0, "hintStock": 50})
    ui.ev(STUB)
    dv = ui.ev("DEV_DEFAULT")
    pick, hover, drop, btn = dv["vibPick"], dv["vibHover"], dv["vibDrop"], dv["vibBtn"]
    ui.check("振動の既定値（つまむ・枠の上・置く・ボタン）", [pick, hover, drop, btn], [16, 10, 24, 15])
    ui.click("gear")
    ui.check("「振動」は既定でオン", ui.ev("$('t-vib').classList.contains('on')"), True)
    vib(ui)
    # ── オン: ボタンで振動する ─────────────────────────────
    ui.click("t-score")
    ui.check("オン: 設定の項目で 1 回", vib(ui), [btn])
    ui.click("navback")
    ui.check("オン: 左上の戻るで 1 回", vib(ui), [btn])
    ui.click("m-course")
    ui.check("オン: ホームのモード選択で 1 回", vib(ui), [btn])
    for el in ["clear", "hint", "share"]:
        ui.ev("Object.defineProperty(navigator,'share',{value:undefined,configurable:true})")  # 共有メニューは開かない（コピーに回る）
        ui.click(el)
        ui.check("オン: 問題画面の #%s で 1 回" % el, vib(ui), [btn])
    ui.click("pcodev")
    ui.check("オン: コードのタップで 1 回", vib(ui), [btn])
    ui.check("オン: 押せない（disabled）ヒントの ‹ では振動しない",
             ui.ev("$('hint-prev').disabled"), True)
    # 合成の click は disabled でも onclick まで届く（段階 0＝閉じる）。実機の指では
    # 届かないが、ここでは「振動の 1 か所」が disabled を数えないことだけを見る
    ui.ev("$('hint-prev').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
    ui.check("オン: disabled のボタンは数えない", vib(ui), [])
    ui.ev("$('hint-close')&&$('hint-close').click()")
    ui.click("clear")
    vib(ui)
    # ── オン: ドラッグ ────────────────────────────────────
    drag_plus(ui)
    log = vib(ui)
    ui.check("ドラッグ: 式に + が置かれた", ui.ev("T().some(x=>x.t==='op'&&x.v==='+')"), True)
    ui.check("ドラッグ: 最初はつまむ長さ", log[:1], [pick])
    ui.check("ドラッグ: 最後は置く長さ", log[-1:], [drop])
    ui.check("ドラッグ: 途中は枠の上の長さだけ",
             all(x == hover for x in log[1:-1]) and len(log) >= 3, True)
    ui.check("ドラッグ: ボタンの振動は混ざらない", btn in log, False)
    # ── 開発者パネルで長さを変える ─────────────────────────
    ui.ev("G.dev=true; devPanelShow(true)")
    ui.check("開発者パネル: ボタンの長さの表示", ui.text("dv-vibBtn-v"), "%dms" % btn)
    ui.check("開発者パネル: つまむ長さの表示", ui.text("dv-vibPick-v"), "%dms" % pick)
    ui.ev("(()=>{const s=$('dv-vibBtn');s.value=40;s.dispatchEvent(new Event('input'))})()")
    ui.check("開発者パネル: 動かすと表示が変わる", ui.text("dv-vibBtn-v"), "40ms")
    vib(ui)
    ui.click("clear")
    ui.check("開発者パネル: 変えた長さでボタンが振動する", vib(ui), [40])
    ui.ev("(()=>{const s=$('dv-vibPick');s.value=33;s.dispatchEvent(new Event('input'))})()")
    ui.ev("devPanelShow(false)")          # パネルはトレイに重なるので閉じてからつまむ
    ui.click("clear")
    vib(ui)
    drag_plus(ui)
    ui.check("開発者パネル: 変えた長さでつまむ", vib(ui)[:1], [33])
    ui.ev("devPanelShow(true)")
    ui.click("dv-reset")
    ui.check("既定値に戻すで振動の長さも戻る",
             ui.ev("[G.devVars.vibPick,G.devVars.vibBtn]"), [pick, btn])
    ui.ev("devPanelShow(false)")
    vib(ui)
    # ── オフ: 何も振動しない ──────────────────────────────
    ui.click("menu")
    ui.check("オン: 問題画面の #menu で 1 回", vib(ui), [btn])
    ui.click("t-vib")
    ui.check("「振動」をオフにした見た目", ui.ev("$('t-vib').classList.contains('on')"), False)
    ui.check("オフにした操作そのものでは振動しない", vib(ui), [])
    ui.click("t-score")
    ui.click("navback")
    for el in ["clear", "hint", "pcodev"]:
        ui.click(el)
    ui.click("clear")
    drag_plus(ui)
    ui.check("オフ: ボタンもドラッグも振動しない", vib(ui), [])
    ui.click("menu")
    ui.click("t-vib")
    ui.check("オンに戻した操作で 1 回", vib(ui), [btn])
    ui.check("オンに戻した見た目", ui.ev("$('t-vib').classList.contains('on')"), True)
    # ── 保存データ: 振動の長さのキーが無い devVars ─────────────
    ui.open({"ci": 0, "cleared": 0, "vib": False,
             "devVars": {"dur": 300, "shrink": 80, "catch": 40, "swapCatch": 40,
                         "hotDur": 200, "zoneMin": 22, "delta": 18, "devTop": 0}})
    ui.check("古い devVars: 振動の長さは既定値で補われる",
             ui.ev("[G.devVars.vibPick,G.devVars.vibHover,G.devVars.vibDrop,G.devVars.vibBtn]"),
             [pick, hover, drop, btn])
    ui.check("「振動」オフの保存が読める", ui.ev("G.vib"), False)
    # ── iPhone（navigator.vibrate が無い）───────────────────
    ui.open({"ci": 0, "cleared": 0})
    ui.ev("Object.defineProperty(navigator,'vibrate',{value:undefined,configurable:true})")
    ui.click("m-course")
    ui.click("clear")
    drag_plus(ui)
    ui.check("vibrate が無くてもボタンとドラッグが動く",
             ui.ev("SCR==='play'&&T().some(x=>x.t==='op')"), True)
    ui.check_no_errors()
