# -*- coding: utf-8 -*-
"""外から入ってくる値（公開前の安全の点検。D0.46〜。DAILY-SPEC 11 章）。

- 保存（localStorage）から読んだ記録と途中の分は、データ移行で受け取るときと同じ確かめに通す。
  null の日・__proto__・形の違う値は捨て、正しい日の記録は残す。統計とカレンダーが開ける（D0.46）
"""
import datetime
import json
import time

from uiharness import daily_ui as dui

NAME = "外から入ってくる値"

TZ = "Asia/Tokyo"
XSS = '<img src=x onerror="window.__X=(window.__X||0)+1">'


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    no = 8
    sol = lambda n: rows[n - 1]["sol"]                                # noqa: E731
    solved = lambda n, t=40, h=0, sh=0: {"r": "s", "t": t, "h": h, "sh": sh, "e": sol(n), "sent": 1}   # noqa: E731

    # ══ 保存から読んだ記録（D0.46）══
    raw = ('{"v":1,"days":{"1":%s,"2":null,"3":5,"4":{"r":"s","t":%s,"h":%s},"x5":%s,"__proto__":{"r":"s","t":1,"h":0},'
           '"6":{"r":"g","t":null,"h":1,"sh":0},"7":[1,2]},'
           '"cur":{"no":%d,"start":"x","h":"9","sh":"<b>"},"set":{"easy":0,"tap":0,"dark":0,"lang":"auto"}}'
           % (json.dumps(solved(1)), json.dumps(XSS), json.dumps(XSS), json.dumps(solved(1)), no))
    ui.open(now=at(no), tz=TZ, store="keep")
    ui.ev("localStorage.clear();localStorage.setItem(%s,%s)" % (json.dumps(dui.SAVE_KEY), json.dumps(raw)))
    ui.open(now=at(no), tz=TZ, store="keep")
    ui.check("保存の形の違う日（null・数字・HTML の時間とヒント・番号が x5・__proto__・配列）は捨て、正しい #1 と #6 は残す",
             ui.ev("JSON.stringify(DATA.days)"),
             json.dumps({"1": {k: v for k, v in solved(1).items()}, "6": {"r": "g", "t": None, "h": 1, "sh": 0}},
                        separators=(",", ":")))
    ui.check("途中の分の形の違う値は既定に戻す（ヒントの回数と共有の回数は 0 の数）",
             ui.ev("[hintUsed,shareCount,typeof hintUsed,typeof shareCount]"), [0, 0, "number", "number"])
    ui.check("プロトタイプは汚れない", ui.ev("[({}).r,({}).t,({}).h]"), [None, None, None])
    ui.ev("dstats.click()")
    time.sleep(0.2)
    ui.check("統計が開き、解いた日数は 1（#1 だけ）", ui.ev("[popNow,$('statlist').querySelector('.stat b').textContent]"),
             ["dstatsheet", "1"])
    ui.ev("const b=document.querySelector('#dcal-grid button.s');if(b)b.click()")
    time.sleep(0.1)
    ui.check("カレンダーで解いた日を選べ、HTML として出るものは無い", ui.ev("[window.__X||0,document.querySelectorAll('img').length]"),
             [0, 0])
    ui.check_no_errors("保存から読んだ記録: JS エラー 0")
