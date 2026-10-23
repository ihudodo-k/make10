# -*- coding: utf-8 -*-
"""2 つのタブ（公開前の総点検の H1。D0.50。DAILY-SPEC 10 章・11 章）。

同じページを 2 つのタブで開いていると、古いタブ（昨日から開いたまま・同じ日のもう 1 つ）が保存を書くときに、
別のタブで解いた日の記録を消していた（書くのは、そのタブが覚えている記録の全部だったため）。
D0.50 から、書く前に保存に今ある記録のうち、そのタブが持っていない日を足す。

別のタブが書いたことは、保存の中身を直に書き換えてまねる（ページから見れば、別のタブが書いたのと同じ）。
"""
import datetime
import json
import time

from uiharness import daily_ui as dui

NAME = "2 つのタブ"

TZ = "Asia/Tokyo"
# 別のタブが、その日の記録を書いた（今ある保存に足して書き直す）
OTHER = ("(()=>{const k=%s,x=JSON.parse(localStorage.getItem(k));x.days[%%s]=%%s;x.cur=null;"
         "localStorage.setItem(k,JSON.stringify(x))})()" % json.dumps(dui.SAVE_KEY))


def run(ui):
    start, rows = dui.page_data()

    def at(n, hour=10):
        d = start + datetime.timedelta(days=n - 1)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    sol = lambda n: rows[n - 1]["sol"]                                # noqa: E731
    rec = lambda n, r="s": ({"r": "s", "t": 42, "h": 0, "sh": 0, "e": sol(n), "sent": 1} if r == "s"   # noqa: E731
                            else {"r": "g", "t": None, "h": 1, "sh": 1, "sent": 1})
    days = lambda: (ui.saved(raw=True) or {}).get("days") or {}       # noqa: E731

    # 1. 同じ日の 2 つ目のタブ: 解かずに置いたタブに 61 分後に戻る（数え直して保存を書く）
    ui.open(now=at(5), tz=TZ)
    ui.ev(OTHER % (json.dumps("5"), json.dumps(rec(5))))
    ui.visibility("hidden")
    ui.tick(61 * 60000)
    ui.visibility("visible")
    time.sleep(0.4)
    ui.check("同じ日: 置いておいたタブが書いても、別のタブで解いた今日の記録が残る",
             days().get("5"), rec(5))
    ui.check("同じ日: 置いておいたタブも、結果の画面になる（途中の分は残さない）",
             [ui.visible("result"), ui.ev("$('play').classList.contains('done')"), (ui.saved(raw=True) or {}).get("cur")],
             [True, True, None])
    ui.check("同じ日: 結果の画面の盤は、別のタブで解いた式", ui.ev("exprOf()"), sol(5))

    # 2. 昨日から開いたままのタブ: 今日、別のタブで解いた後に、昨日のタブへ戻る
    ui.open(now=at(5), tz=TZ)
    ui.ev(OTHER % (json.dumps("6"), json.dumps(rec(6))))
    ui.visibility("hidden")
    ui.tick(24 * 3600000)
    ui.visibility("visible")
    time.sleep(0.4)
    ui.check("昨日のタブ: 戻っても、今日（#6）の記録が残る", days().get("6"), rec(6))
    ui.check("昨日のタブ: 昨日（#5）は遊んでいる途中のまま", [ui.visible("result"), (ui.saved(raw=True) or {}).get("cur", {}).get("no")],
             [False, 5])

    # 3. 解いた後のタブで設定を変える・共有する（解いた後の書き込み）
    ui.open(now=at(6), tz=TZ, store={"v": 1, "days": {"5": rec(5)}, "cur": None})
    ui.ev(OTHER % (json.dumps("7"), json.dumps(rec(7, "g"))))
    ui.ev("dset.click()")
    ui.ev("$('t-easy').click()")
    ui.check("設定を変えても、別のタブの #7 が残る", days().get("7"), rec(7, "g"))
    ui.check("設定は書けている", (ui.saved(raw=True) or {}).get("set", {}).get("easy"), 1)

    # 4. どちらにもある日は、このタブの分を残す（送れたかの印だけ足す）
    ui.open(now=at(6), tz=TZ, store={"v": 1, "days": {"5": {**rec(5), "sent": 0}}, "cur": None})
    ui.ev(OTHER % (json.dumps("5"), json.dumps({**rec(5, "g")})))
    ui.ev("$('t-tap').click()")
    ui.check("どちらにもある日は、このタブの記録を残し、sent は付いていれば付ける", days().get("5"), rec(5))

    # 5. 保存にある形の違う日は足さない（読み込みと同じ確かめ）
    ui.open(now=at(6), tz=TZ)
    ui.ev("(()=>{const k=%s,x=JSON.parse(localStorage.getItem(k));x.days['1']={r:'s',t:'<b>',h:0};x.days['x2']=%s;"
          "x.days['9']=%s;localStorage.setItem(k,JSON.stringify(x))})()"
          % (json.dumps(dui.SAVE_KEY), json.dumps(rec(2)), json.dumps(rec(9))))
    ui.ev("$('t-tap').click()")
    ui.check("形の違う日・番号の形の違う日は足さない", sorted(days()), ["9"])
    ui.check_no_errors()
