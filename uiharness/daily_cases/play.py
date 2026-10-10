# -*- coding: utf-8 -*-
"""盤・正解の判定・制約がある日（D0.2）。

解答例を組むと、金の「10」と「正解」になる。記号は `canPut()` を通して置く（ページの操作と同じ道）。
期待値の列は、ページのソースから読む。
"""
import datetime
import time

from uiharness import daily_ui as dui

NAME = "盤と正解の判定"


def mouse(ui, typ, x, y):
    ui.c.ws.call("Input.dispatchMouseEvent",
                 {"type": typ, "x": x, "y": y, "button": "left",
                  "buttons": 1 if typ != "mouseReleased" else 0, "clickCount": 1})


def center(ui, sel):
    return ui.ev("(()=>{const b=document.querySelector(%r).getBoundingClientRect();"
                 "return [b.left+b.width/2,b.top+b.height/2]})()" % sel)

GOLD = "rgb(227, 193, 111)"                      # --gold（藍）。金を使うのは正解の「10」だけ
OPS = {"A": "+", "S": "−", "M": "×", "D": "÷", "P": "^", "F": "!"}     # 画面に出る記号
RAW = {"A": "+", "S": "-", "M": "*", "D": "/", "P": "^", "F": "!"}     # トレイの data-op
STATE = ("(function(){const e=document.getElementById('eq');return ["
         "e.textContent,document.getElementById('sub').textContent,"
         "e.classList.contains('hit'),e.classList.contains('ban'),e.classList.contains('miss')]})()")


def run(ui):
    start, rows = dui.page_data()
    iso = lambda n: (start + datetime.timedelta(days=n - 1)).isoformat()   # noqa: E731

    # ── 最初の 2 週（14 問）: 解答例を組むと正解になる ──
    bad, ban_bad = [], []
    for r in rows[:14]:
        ui.open(date=iso(r["no"]))
        got = ui.solve(r["sol"])
        st = ui.ev(STATE)
        if got != "10|正解" or st[2:] != [True, False, False]:
            bad.append((r["no"], r["sol"], got, st))
        # 制約がある日の 1 行と、トレイの使えない記号
        line = ui.text("banline")
        off = ui.ev("[...document.querySelectorAll('#tray .chip.off')].map(e=>e.dataset.op).join(' ')")
        if r["rc"] == "N":
            if line != "" or off != "":
                ban_bad.append((r["no"], r["rc"], line, off))
        elif line != OPS[r["rc"][0]] + " は使えません" or off != RAW[r["rc"][0]]:
            ban_bad.append((r["no"], r["rc"], line, off))
    ui.check("最初の 14 問: 解答例を組むと「10」と「正解」", bad, [])
    ui.check("最初の 14 問: 制約がある日だけ 1 行が出て、トレイのその記号が使えない", ban_bad, [])
    ui.check("最初の 14 問に、制約がある日と無い日の両方がある",
             [any(r["rc"] == "N" for r in rows[:14]), any(r["rc"] != "N" for r in rows[:14])],
             [True, True])

    # ── 1 問を細かく見る（#1）──
    r = rows[0]
    # 公開初日の問題（D0.12）: いちばんやさしい難易度 6・制約なし・解答例に 0! も階乗も累乗も無い。同じ 4 桁は列に 1 度だけ
    ui.check("#1（公開初日）: 難易度 6・制約なし・解答例に ! と ^ が無い・4 桁は列に 1 度だけ",
             [r["d"], r["rc"], "!" in r["sol"], "^" in r["sol"], [x["id"] for x in rows].count(r["id"])],
             [6, "N", False, False, 1])
    ui.open(date=iso(1))
    ui.check("解く前: 読み出し行は空で、金はどこにも無い",
             [ui.ev(STATE)[:2], ui.ev("[...document.querySelectorAll('#app *')].filter("
                                      "e=>getComputedStyle(e).color===%r).length" % GOLD)],
             [["", ""], 0])
    ui.solve(r["sol"], wait=0.9)
    ui.check("正解: 「10」と「正解」", ui.ev(STATE), ["10", "正解", True, False, False])
    ui.check("正解: 「10」は金", ui.ev("getComputedStyle(eq).color"), GOLD)
    ui.check("正解: 金を使っているのは「10」だけ",
             ui.ev("[...document.querySelectorAll('#app *')].filter("
                   "e=>getComputedStyle(e).color===%r).map(e=>e.id)" % GOLD), ["eq"])
    ui.check("正解: 「10」は拡大して出る（本編と同じ倍率）",
             ui.ev("getComputedStyle(eq).transform"), "matrix(1.8, 0, 0, 1.8, 0, 0)")
    ui.check("正解: 記録の旗が立つ（1 回だけ）", ui.ev("solved"), True)
    ui.check("正解のあともスクロールしない", ui.scrolls(), False)
    # 全解答のどれを組んでも正解になる
    wrong = []
    for sol in r["sols"]:
        ui.open(date=iso(1))
        got = ui.solve(sol, wait=0.05)
        if got != "10|正解":
            wrong.append((sol, got))
    ui.check("#1 の全解答（%d 本）は、どれを組んでも正解" % len(r["sols"]), wrong, [])

    # ── 10 でない式・途中の式 ──
    ui.open(date=iso(1))
    a, b, c, d = r["id"]
    got = ui.solve("%s + %s + %s + %s" % (a, b, c, d), wait=0.1)
    total = sum(map(int, r["id"]))
    if total != 10:
        ui.check("10 でない式: 値が出て、正解にならない",
                 [got, ui.ev(STATE)[2:], ui.ev("solved")], ["%d|" % total, [False, False, True], False])
    ui.ev("clearAll()")
    ui.ev("put('+',1);render()")
    ui.check("記号が 3 つ揃うまでは、読み出し行は空", ui.ev(STATE)[:2], ["", ""])
    ui.ev("clearAll();put('lp',0);put('+',2);put('+',4);put('+',6);render()")
    ui.check("括弧が対応していないときの注意", ui.ev(STATE)[:2],
             ["括弧が対応していません", "赤い括弧が余っています"])

    # ── 制約がある日: 使えない記号で 10 を作っても正解にならない ──
    # 使えない記号を使って 10 になる式（括弧なし・+ - * / だけ）が作れる日を、列の頭から探す
    def banned_ten(x):
        op, ds = RAW[x["rc"][0]], x["id"]
        if op not in "+-*/":
            return None
        for o1 in "+-*/":
            for o2 in "+-*/":
                for o3 in "+-*/":
                    if op not in (o1, o2, o3):
                        continue
                    expr = "%s %s %s %s %s %s %s" % (ds[0], o1, ds[1], o2, ds[2], o3, ds[3])
                    try:
                        if abs(eval(expr) - 10) < 1e-9:
                            return expr
                    except ZeroDivisionError:
                        pass
        return None

    con, found = next(((x, banned_ten(x)) for x in rows[:400]
                       if x["rc"] != "N" and banned_ten(x)), (None, None))
    ui.check("使えない記号で 10 が作れる日が、列の頭 400 問の中にある", found is not None, True)
    if found:
        ui.open(date=iso(con["no"]))
        ui.solve(found, wait=0.1)
        ui.check("制約がある日（#%d %s）: 使えない記号で 10 を作っても正解にならない"
                 % (con["no"], con["rc"]),
                 [ui.ev(STATE), ui.ev("solved")],
                 [["10", OPS[con["rc"][0]] + " は使えません", False, True, False], False])
        ui.check("そのとき「10」は金でない", ui.ev("getComputedStyle(eq).color") != GOLD, True)
    # ── 本物の操作（マウスのドラッグ）で置く・外す ──
    ui.open(date=iso(1))
    x0, y0 = center(ui, '.chip[data-op="+"]')
    mouse(ui, "mousePressed", x0, y0)
    time.sleep(0.4)                                   # 置ける場所の枠が開くのを待つ
    ui.check("つまむと、置ける場所の枠が 3 つ開く",
             ui.ev("document.querySelectorAll('.zone.live').length"), 3)
    x1, y1 = center(ui, ".zone.live")
    for i in range(1, 9):
        mouse(ui, "mouseMoved", x0 + (x1 - x0) * i / 8, y0 + (y1 - y0) * i / 8)
        time.sleep(0.03)
    time.sleep(0.2)
    mouse(ui, "mouseReleased", x1, y1)
    time.sleep(0.5)
    ui.check("ドラッグで + が 1 つ目の隙間に入る",
             ui.ev("T().map(x=>x.t==='num'?x.v:x.t==='op'?x.v:x.t).join(' ')"),
             "%s + %s %s %s" % tuple(rows[0]["id"]))
    ui.check("置いたあと、枠は閉じる", ui.ev("document.querySelectorAll('.zone.live').length"), 0)
    # 置いた記号を、式のエリアの外（上のバー）へ運ぶと外れる
    x0, y0 = center(ui, "#expr .tok.op")
    x1, y1 = center(ui, "#dinfo")
    mouse(ui, "mousePressed", x0, y0)
    time.sleep(0.3)
    for i in range(1, 9):
        mouse(ui, "mouseMoved", x0 + (x1 - x0) * i / 8, y0 + (y1 - y0) * i / 8)
        time.sleep(0.03)
    ui.check("外へ運んでいる間、外れる合図が出る",
             ui.ev("document.getElementById('field').classList.contains('trash')"), True)
    mouse(ui, "mouseReleased", x1, y1)
    time.sleep(0.5)
    ui.check("外で離すと記号が外れる", ui.ev("T().length"), 4)
    ui.check_no_errors()
