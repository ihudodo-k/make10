# -*- coding: utf-8 -*-
"""式が出来るまでの、薄い「10」（D0.35。DAILY-SPEC 13-1）。

「途中の値を表示」がオフのとき、記号が 2 つ以下の間は、読み出し行に目標の「10」を無効の色（--slate）で置いておく。
正解した瞬間は、同じ場所の「10」が金になって大きくなるだけで、何も無い所に急に出てこない。

- 開いた直後・記号 1 つ・2 つ・全部消した後は、薄い「10」（大きさは正解の「10」の拡大前と同じ・拡大しない・下の行は空）
- 3 つ置いて 10 でない値なら、その値（薄い「10」は消える）
- 正解の瞬間、「10」は同じ場所（下端と横の中央）から大きくなり、金になる
- 白とダークモードの両方で、色は --slate
- 英語でも「10」
- 途中の値がオンのときは出さない（途中の値が出る）
"""
import datetime
import json
import time

from uiharness import daily_ui as dui
from uiharness.daily_cases.win_line import PREP

NAME = "式が出来るまでの薄い 10"

TZ = "Asia/Tokyo"
SLATE_DARK = "rgb(95, 96, 100)"
SLATE_LIGHT = "rgb(163, 167, 173)"
GOLD_DARK = "rgb(220, 189, 110)"
STATE = "[eq.textContent,eq.className,sub.textContent]"
# 拡大前の「10」の大きさ（.eq の字の大きさ）と、今の読み出し行の字の大きさ・transform
SIZE = ("(function(){const d=document.createElement('div');d.className='eq';eq.parentElement.appendChild(d);"
        "const f=getComputedStyle(d).fontSize;d.remove();const s=getComputedStyle(eq);"
        "return [s.fontSize===f,s.fontWeight,s.transform]})()")
# 最後の 1 手の前（薄い「10」）と、置いた直後（正解の「10」）の、下端と横の中央
FIRE = ("(function(){const r=e=>{const b=e.getBoundingClientRect();return [b.bottom,(b.left+b.right)/2,b.height]};"
        "const a=r(eq),ca=eq.className;put(__last[0],__last[1]);render();const b=r(eq);"
        "return {ca,cb:eq.className,db:Math.abs(a[0]-b[0]),dx:Math.abs(a[1]-b[1]),grow:b[2]/a[2]}})()")


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    # 解答例に括弧と階乗が無い日（最後の 1 手の前は記号が 2 つで、薄い「10」が出ている）
    row = next(r for r in rows if "(" not in r["sol"] and "!" not in r["sol"])
    no = row["no"]
    d = row["id"]
    # 10 にならない式（4 つの数字を足すか掛ける）
    miss = next(e for e in ("%s + %s + %s + %s" % tuple(d), "%s * %s * %s * %s" % tuple(d), "%s + %s * %s + %s" % tuple(d))
                if eval(e) != 10)

    # ══ ダークモード（ケースの既定）══
    ui.open(now=at(no), tz=TZ)
    ui.check("開いた直後: 目標の「10」を薄く出す・下の行は空", ui.ev(STATE), ["10", "eq goal", ""])
    ui.check("色は無効の色（--slate）", ui.ev("getComputedStyle(eq).color"), SLATE_DARK)
    ui.check("大きさは正解の「10」の拡大前と同じ・太字・拡大しない", ui.ev(SIZE), [True, "700", "none"])
    ui.ev("put('+',1);render()")
    ui.check("記号 1 つ: 薄い「10」のまま", ui.ev(STATE), ["10", "eq goal", ""])
    ui.ev("put('+',3);render()")
    ui.check("記号 2 つ: 薄い「10」のまま", ui.ev(STATE), ["10", "eq goal", ""])
    ui.ev("clearAll();render()")
    ui.check("全部消すと、薄い「10」に戻る", ui.ev(STATE), ["10", "eq goal", ""])
    got = ui.solve(miss)
    ui.check("3 つ置いて 10 でない値なら、その値を出す（薄い「10」は消える）",
             [got.split("|")[0] == str(eval(miss)), "goal" in ui.ev("eq.className")], [True, False])
    ui.ev("clearAll();render()")
    ui.check("消すと、また薄い「10」", ui.ev(STATE), ["10", "eq goal", ""])

    # 正解の瞬間: 同じ場所から大きくなる
    ui.ev(PREP + "(%s)" % json.dumps(row["sol"]))
    ui.check("最後の 1 手の前: 薄い「10」", ui.ev(STATE), ["10", "eq goal", ""])
    f = ui.ev(FIRE)
    ui.check("正解の瞬間: 薄い「10」から正解の「10」に替わり、下端と横の中央は動かず、大きくなる",
             [f["ca"], f["cb"], f["db"] < 1, f["dx"] < 1, (f["grow"] or 0) > 1.5], ["eq goal", "eq hit", True, True, True])
    time.sleep(0.5)
    ui.check("正解の後は金", ui.ev("getComputedStyle(eq).color"), GOLD_DARK)

    # ══ 白 ══
    ui.open(now=at(no), tz=TZ, dark=False)
    ui.check("白: 薄い「10」で、色は白の --slate", [ui.ev(STATE), ui.ev("getComputedStyle(eq).color")],
             [["10", "eq goal", ""], SLATE_LIGHT])

    # ══ 英語 ══
    ui.open(now=at(no), tz=TZ, lang="en")
    ui.check("英語でも「10」", ui.ev(STATE), ["10", "eq goal", ""])

    # ══ 途中の値がオンのとき ══
    ui.ev("G.easy=true;render()")
    ui.check("途中の値がオン: 薄い「10」は出さず、途中の値を出す", "goal" in ui.ev("eq.className"), False)
    ui.ev("G.easy=false;render()")
    ui.check_no_errors()
